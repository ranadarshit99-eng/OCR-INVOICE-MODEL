import sys
import os

sys.path.insert(0, 'd:/Desktop/AI PROJECT OCR MODEL/backend')
from ocr_engine import OCREngine
from extractor import InvoiceExtractor

with open('d:/Desktop/AI PROJECT OCR MODEL/backend/uploads/batch1-0001.jpg', 'rb') as f:
    data = f.read()

ocr = OCREngine()
res = ocr.process_file(data, 'batch1-0001.jpg')
print("=== FULL OCR TEXT ===")
print(res.get('text', ''))

ext = InvoiceExtractor()
fin = ext.extract_financials(res.get('text', ''))
print("\n=== EXTRACTED FINANCIALS ===")
print(fin)

curr = ext.detect_currency(res.get('text', ''))
print("\n=== DETECTED CURRENCY ===")
print(curr)

proc = ext.process(res)
print("\n=== DETECTED FIELDS ===")
for df in proc.get("detected_fields", []):
    print(f"[{df['category']}] {df['label']}: {df['value']}")

