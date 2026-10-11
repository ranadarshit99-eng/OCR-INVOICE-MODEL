from sample_generator import generate_sample_invoice_image
from ocr_engine import OCREngine
import time

print("Generating sample invoice image...")
img_bytes = generate_sample_invoice_image()

print("Processing invoice with OCREngine...")
engine = OCREngine()
t0 = time.time()
res = engine.process_file(img_bytes, "sample.png")
t1 = time.time()

print(f"\n--- OCR COMPLETED IN {t1-t0:.2f}s ---")
print("Average Confidence:", res["average_confidence"])
print("Word Count:", len(res["words_with_boxes"]))
print("Stamp/Signature Info:", res["stamp_signature"])
print("\n--- EXTRACTED RAW TEXT ---")
print(res["text"])
