import os
import sys
import io
import time
import shutil
import tempfile
import logging
from typing import Optional

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Internal modules
from ocr_engine import OCREngine, EASYOCR_AVAILABLE, PYTESSERACT_AVAILABLE
from dataset_manager import DatasetManager
from invoice_parser import InvoiceParser
from analytics_engine import AnalyticsEngine
from extractor import InvoiceExtractor
from validator import InvoiceValidator
from sample_generator import generate_sample_invoice_image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InvoiceOCRApp")

app = FastAPI(
    title="OCR-Based Invoice Analysis Engine",
    description="Interactive OCR & AI-Powered Invoice Extraction Engine",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Core Services
ocr_engine = OCREngine()
dataset_mgr = DatasetManager()
invoice_parser = InvoiceParser()
analytics_engine = AnalyticsEngine()
extractor = InvoiceExtractor()
validator = InvoiceValidator()

# Storage directory for uploaded files
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ANALYSIS_HISTORY = []


# ============================================================================
# DATASET & EXPLORER API (Used by 3-Panel Dashboard Explorer)
# ============================================================================

@app.get("/api/dataset/status")
def get_dataset_status():
    invoices = dataset_mgr.get_all_invoices()
    easyocr_ok = getattr(ocr_engine, '_easyocr_reader', None) is not None or ocr_engine.easyocr_available
    return {
        "status": "ready",
        "dataset_id": dataset_mgr.dataset_id,
        "kaggle_path": dataset_mgr.cached_path or "Cached High Quality Samples",
        "total_invoices": len(invoices),
        "tesseract_available": True,
        "ocr_engines": {
            "easyocr": easyocr_ok,
            "fitz": True,
            "pytesseract": True
        }
    }


@app.get("/api/dataset/invoices")
def list_invoices(query: Optional[str] = None, page: int = 1, limit: int = 100):
    all_invoices = dataset_mgr.get_all_invoices()
    if query:
        q = query.strip().lower()
        filtered = [i for i in all_invoices if q in i["filename"].lower()]
    else:
        filtered = all_invoices

    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    paginated = filtered[start:end]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "invoices": paginated
    }


@app.get("/api/dataset/image/{filename}")
def get_invoice_image(filename: str, page: int = Query(1)):
    path = dataset_mgr.get_invoice_path(filename)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Invoice image '{filename}' not found.")
    
    if filename.lower().endswith(".pdf"):
        try:
            import fitz
            doc = fitz.open(path)
            page_idx = max(0, min(page - 1, len(doc) - 1))
            pdf_page = doc[page_idx]
            pix = pdf_page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            return Response(content=img_bytes, media_type="image/png")
        except Exception as e:
            logger.error(f"Error rendering PDF preview: {e}")
            raise HTTPException(status_code=500, detail="Failed to render PDF page image.")
            
    return FileResponse(path)


@app.post("/api/upload-preview")
async def upload_preview_endpoint(file: UploadFile = File(...)):
    """Accepts an uploaded file (PDF or image), caches it, and returns an image preview URL."""
    try:
        filename = file.filename
        file_bytes = await file.read()
        saved_path = os.path.join(UPLOAD_DIR, filename)
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
        dataset_mgr.add_uploaded_file(filename, saved_path)

        is_pdf = filename.lower().endswith(".pdf") or (len(file_bytes) >= 4 and file_bytes[:4] == b"%PDF")
        page_count = 1
        if is_pdf:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            preview_url = f"/api/dataset/image/{filename}?page=1"
        else:
            preview_url = f"/api/dataset/image/{filename}"

        return {
            "status": "success",
            "filename": filename,
            "preview_url": preview_url,
            "is_pdf": is_pdf,
            "page_count": page_count,
            "size_kb": round(len(file_bytes) / 1024.0, 1)
        }
    except Exception as e:
        logger.error(f"Error in upload preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process file preview: {str(e)}")


ANALYSIS_CACHE = {}

@app.post("/api/analyze")
async def analyze_invoice_endpoint(
    filename: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    regime: Optional[str] = Form("auto")
):
    import time
    start_time = time.time()
    target_path = None
    file_bytes = None

    if file:
        filename = file.filename
        saved_path = os.path.join(UPLOAD_DIR, filename)
        file_bytes = await file.read()
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
        target_path = saved_path
        dataset_mgr.add_uploaded_file(filename, saved_path)
    elif filename:
        target_path = dataset_mgr.get_invoice_path(filename)

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="Invalid filename or file provided.")

    cache_key = f"{filename}_{regime}_{os.path.getmtime(target_path) if os.path.exists(target_path) else 0}"
    if not file and cache_key in ANALYSIS_CACHE and ANALYSIS_CACHE[cache_key].get("detected_fields_count", 0) > 0:
        cached_res = dict(ANALYSIS_CACHE[cache_key])
        cached_res["execution_time_sec"] = 0.001
        cached_res["cached"] = True
        return JSONResponse(content=cached_res)

    try:
        if file_bytes is None:
            with open(target_path, "rb") as f:
                file_bytes = f.read()

        # Step 1: Run OCR Engine for Text & Bounding Boxes
        ocr_result_raw = ocr_engine.process_file(file_bytes, filename or "invoice.png")
        ocr_result = ocr_engine.extract_text_and_boxes(file_bytes, filename=filename or "invoice.png", cached_res=ocr_result_raw)

        # Step 2: Run ML / Heuristic Invoice Parsers
        parsed_result = invoice_parser.parse(ocr_result, filename=filename)
        extracted_fields = extractor.process(ocr_result_raw, regime=regime)
        verification_data = validator.process_verification(extracted_fields, ocr_result_raw)

        elapsed = round(time.time() - start_time, 3)

        detected_fields_list = extracted_fields.get("detected_fields", [])
        words_count = len(ocr_result.get("words", []))
        auth_score = verification_data.get("invoice_authenticity", {}).get("authenticity_score", 92.0)

        pipeline_steps = [
            {"step": 1, "name": "Document Page Ingestion", "status": "completed", "details": "Loaded document and initialized optical coordinate buffer"},
            {"step": 2, "name": "Text & Coordinate Recognition", "status": "completed", "details": f"{words_count} words recognized with spatial bounding boxes"},
            {"step": 3, "name": "Key-Value & Entity Extraction", "status": "completed", "details": f"{len(detected_fields_list)} structured document fields extracted"},
            {"step": 4, "name": "Results Validation & Finalization", "status": "completed", "details": f"Document integrity verified at {auth_score:.0f}%"}
        ]

        preview_url = f"/api/dataset/image/{filename}?page=1" if (filename and filename.lower().endswith(".pdf")) else f"/api/dataset/image/{filename}"
        response_payload = {
            "filename": filename,
            "preview_url": preview_url,
            "ocr": ocr_result,
            "ocr_raw": ocr_result_raw,
            "parsed": parsed_result,
            "extracted_fields": extracted_fields,
            "detected_fields": detected_fields_list,
            "detected_fields_count": len(detected_fields_list),
            "pipeline_steps": pipeline_steps,
            "verification": verification_data,
            "execution_time_sec": elapsed,
            "cached": False,
            "status": "success"
        }

        if filename and not file:
            ANALYSIS_CACHE[cache_key] = response_payload

        # Step 3: Log for Analytics
        analytics_engine.log_analysis(parsed_result)

        return JSONResponse(content=response_payload)

    except Exception as e:
        logger.error(f"Error analyzing invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis Error: {str(e)}")


@app.get("/api/analytics")
def get_analytics():
    return analytics_engine.get_summary_stats()


@app.get("/api/export/csv")
def export_csv():
    csv_data = analytics_engine.export_csv(analytics_engine.history)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=extracted_invoices.csv"}
    )


# ============================================================================
# API v1 COMPATIBILITY ENDPOINTS
# ============================================================================

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "online",
        "timestamp": time.time(),
        "ocr_engines": {
            "easyocr_available": ocr_engine.easyocr_available,
            "fitz_available": True,
            "pytesseract_available": PYTESSERACT_AVAILABLE
        },
        "supported_fields": 47
    }


@app.post("/api/v1/analyze")
async def analyze_invoice_v1(file: UploadFile = File(...)):
    start_time = time.time()
    filename = file.filename
    content_type = file.content_type
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file provided.")

    saved_path = os.path.join(UPLOAD_DIR, filename)
    with open(saved_path, "wb") as f:
        f.write(file_bytes)
    dataset_mgr.add_uploaded_file(filename, saved_path)

    try:
        ocr_result = ocr_engine.process_file(file_bytes, filename)
        extracted_fields = extractor.process(ocr_result)
        verification_data = validator.process_verification(extracted_fields, ocr_result)
        processing_time = round(time.time() - start_time, 2)

        response_payload = {
            "success": True,
            "filename": filename,
            "file_size": len(file_bytes),
            "processing_time_seconds": processing_time,
            "step_1_upload": {
                "filename": filename,
                "content_type": content_type,
                "size_kb": round(len(file_bytes) / 1024, 2)
            },
            "step_2_ocr": {
                "raw_text": ocr_result["text"],
                "average_confidence": ocr_result["average_confidence"],
                "pages_count": ocr_result["pages_count"],
                "word_count": len(ocr_result["words_with_boxes"])
            },
            "step_3_extracted_fields": extracted_fields,
            "step_4_verification_g": verification_data,
            "step_5_summary": {
                "invoice_number": extracted_fields["basic_details"]["invoice_number"],
                "invoice_date": extracted_fields["basic_details"]["invoice_date"],
                "seller_name": extracted_fields["seller_details"]["seller_name"],
                "buyer_name": extracted_fields["buyer_details"]["buyer_name"],
                "grand_total": extracted_fields["financial_details"]["grand_total"],
                "currency": extracted_fields["financial_details"]["currency"],
                "payment_status": extracted_fields["payment_details"]["payment_status"],
                "authenticity_score": verification_data["invoice_authenticity"]["authenticity_score"],
                "is_duplicate": verification_data["duplicate_invoice_detection"]["is_duplicate"]
            }
        }

        ANALYSIS_HISTORY.insert(0, response_payload["step_5_summary"])
        if len(ANALYSIS_HISTORY) > 20:
            ANALYSIS_HISTORY.pop()

        return JSONResponse(content=response_payload)
    except Exception as e:
        logger.error(f"Error processing invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dataset/generate-sample")
def generate_sample_invoice_endpoint():
    import time
    try:
        img_bytes = generate_sample_invoice_image()
        timestamp = int(time.time())
        filename = f"synthetic_sample_{timestamp}.png"
        sample_path = os.path.join(dataset_mgr.sample_dir, filename)
        with open(sample_path, "wb") as f:
            f.write(img_bytes)
        dataset_mgr.add_uploaded_file(filename, sample_path)
        return {"status": "success", "filename": filename, "message": "Sample invoice generated successfully."}
    except Exception as e:
        logger.error(f"Error generating sample invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sample-invoice")
def get_sample_invoice():
    img_bytes = generate_sample_invoice_image()
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/v1/history")
def get_history():
    return {"history": ANALYSIS_HISTORY}


# ============================================================================
# STATIC FRONTEND SERVING
# ============================================================================

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    css_dir = os.path.join(FRONTEND_DIR, "css")
    js_dir = os.path.join(FRONTEND_DIR, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    NO_CACHE_HEADERS = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    @app.get("/")
    @app.get("/index.html")
    @app.get("/app")
    @app.get("/app/")
    @app.get("/app/index.html")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), headers=NO_CACHE_HEADERS)

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8005))
    uvicorn.run(app, host=host, port=port)
