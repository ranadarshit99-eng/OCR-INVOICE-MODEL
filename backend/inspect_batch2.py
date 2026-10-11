import sys
sys.path.insert(0, 'backend')
from ocr_engine import OCREngine
from extractor import InvoiceExtractor
import json

ocr = OCREngine()
with open('backend/uploads/batch2-0872.jpg', 'rb') as f:
    file_bytes = f.read()

raw = ocr.process_file(file_bytes, 'batch2-0872.jpg')
print("=== RAW OCR TEXT ===")
print(raw.get('text'))

ext = InvoiceExtractor()
res = ext.process(raw, regime='auto')
print("\n=== FINANCIAL DETAILS ===")
print(json.dumps(res.get('financial_details'), indent=2))

print("\n=== DETECTED FIELDS ===")
for df in res.get('detected_fields', []):
    print(f"[{df.get('category')}] {df.get('label')}: {df.get('value')} (Conf: {df.get('confidence')})")
