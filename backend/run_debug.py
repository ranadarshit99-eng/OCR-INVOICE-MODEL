import os
import sys
import json
import traceback

log_file = "d:/Desktop/AI PROJECT OCR MODEL/backend/debug_test_run.txt"

with open(log_file, "w", encoding="utf-8") as out:
    try:
        sys.path.insert(0, "d:/Desktop/AI PROJECT OCR MODEL/backend")
        from ocr_engine import OCREngine
        from extractor import InvoiceExtractor
        from invoice_parser import InvoiceParser
        from validator import InvoiceValidator

        ocr = OCREngine()
        ext = InvoiceExtractor()
        parser = InvoiceParser()
        val = InvoiceValidator()

        uploads_dir = "d:/Desktop/AI PROJECT OCR MODEL/backend/uploads"
        files = [
            "batch1-0001.jpg",
            "MSME_PERSON_1.pdf",
            "sample_invoice_01.png"
        ]

        for fname in files:
            fpath = os.path.join(uploads_dir, fname)
            if not os.path.exists(fpath):
                fpath = os.path.join("d:/Desktop/AI PROJECT OCR MODEL/samples", fname)
            if not os.path.exists(fpath):
                out.write(f"File not found: {fname}\n")
                continue

            out.write(f"\n================ TESTING {fname} ================\n")
            with open(fpath, "rb") as f:
                data = f.read()

            out.write(f"File size: {len(data)} bytes\n")

            # 1. Test ocr.process_file
            try:
                raw = ocr.process_file(data, fname)
                out.write(f"ocr.process_file SUCCESS. text len: {len(raw.get('text', ''))}, words: {len(raw.get('words_with_boxes', []))}\n")
                out.write(f"Text preview:\n{raw.get('text', '')[:300]}\n")
            except Exception as e:
                out.write(f"ocr.process_file ERROR: {e}\n{traceback.format_exc()}\n")
                raw = {"text": "", "words_with_boxes": []}

            # 2. Test ocr.extract_text_and_boxes
            try:
                # Notice we pass data
                boxes_res = ocr.extract_text_and_boxes(data)
                out.write(f"ocr.extract_text_and_boxes SUCCESS: words={len(boxes_res.get('words', []))}\n")
            except Exception as e:
                out.write(f"ocr.extract_text_and_boxes ERROR: {e}\n{traceback.format_exc()}\n")

            # 3. Test extraction
            try:
                extracted = ext.process(raw)
                detected = extracted.get("detected_fields", [])
                out.write(f"Detected fields: {len(detected)}\n")
                for item in detected:
                    out.write(f"  [{item['category']}] {item['label']}: {item['value']}\n")
            except Exception as e:
                out.write(f"ext.process ERROR: {e}\n{traceback.format_exc()}\n")

    except Exception as e:
        out.write(f"GLOBAL ERROR: {e}\n{traceback.format_exc()}\n")
