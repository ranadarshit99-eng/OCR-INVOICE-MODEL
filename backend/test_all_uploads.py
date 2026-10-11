import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from ocr_engine import OCREngine
from extractor import InvoiceExtractor
from invoice_parser import InvoiceParser

ocr = OCREngine()
ext = InvoiceExtractor()
parser = InvoiceParser()

test_files = [
    "backend/uploads/MSME_PERSON_1.pdf",
    "backend/uploads/batch1-0001.jpg",
    "backend/uploads/CN_Question Bank.pdf"
]

for fp in test_files:
    if not os.path.exists(fp):
        print("Missing file:", fp)
        continue
    print(f"\n==================== TESTING: {fp} ====================")
    with open(fp, "rb") as f:
        data = f.read()
    
    ocr_res = ocr.process_file(data, os.path.basename(fp))
    boxes_res = ocr.extract_text_and_boxes(data, os.path.basename(fp))
    parsed = parser.parse(boxes_res, filename=os.path.basename(fp))
    extracted = ext.process(ocr_res)
    
    detected = extracted.get("detected_fields", [])
    print(f"Total Words Detected: {len(boxes_res.get('words', []))}")
    print(f"Total Detected Fields: {len(detected)}")
    for d in detected[:12]:
        print(f"  • [{d['category']}] {d['label']}: {d['value']}")
