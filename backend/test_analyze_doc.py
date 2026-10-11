import os
import sys
import json

from ocr_engine import OCREngine
from extractor import InvoiceExtractor
from invoice_parser import InvoiceParser
from validator import StatutoryValidator

ocr = OCREngine()
ext = InvoiceExtractor()
parser = InvoiceParser()
val = StatutoryValidator()

uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
for fname in ["batch1-0001.jpg", "MSME_PERSON_1.pdf", "sample_invoice.png"]:
    fpath = os.path.join(uploads_dir, fname)
    if not os.path.exists(fpath):
        continue
    print(f"\n================ TESTING {fname} ================")
    with open(fpath, "rb") as f:
        file_bytes = f.read()

    ocr_raw = ocr.process_file(file_bytes, fname)
    print(f"OCR raw text len: {len(ocr_raw.get('text', ''))}, words: {len(ocr_raw.get('words_with_boxes', []))}")
    print(f"Sample text snippet: {ocr_raw.get('text', '')[:200]}")

    ocr_res = ocr.extract_text_and_boxes(file_bytes)
    print(f"extract_text_and_boxes words: {len(ocr_res.get('words', []))}")

    parsed = parser.parse(ocr_res, filename=fname)
    extracted = ext.process(ocr_raw)
    detected = extracted.get("detected_fields", [])
    print(f"Detected fields count: {len(detected)}")
    for d in detected[:5]:
        print(f"  - {d['label']}: {d['value']}")
