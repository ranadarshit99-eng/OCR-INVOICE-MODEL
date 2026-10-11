from ocr_engine import OCREngine
from extractor import InvoiceExtractor
from validator import InvoiceValidator
from sample_generator import generate_sample_invoice_image
import json

img_bytes = generate_sample_invoice_image()
engine = OCREngine()
ocr_res = engine.process_file(img_bytes, "sample.png")

extractor = InvoiceExtractor()
extracted = extractor.process(ocr_res)

validator = InvoiceValidator()
verif = validator.process_verification(extracted, ocr_res)

print("--- EXTRACTED FIELDS ---")
print(json.dumps(extracted, indent=2))

print("\n--- VERIFICATION DATA ---")
print(json.dumps(verif["invoice_authenticity"], indent=2))
