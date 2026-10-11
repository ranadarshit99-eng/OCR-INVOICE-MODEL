import time
import easyocr

print("Initializing EasyOCR Reader...")
t0 = time.time()
try:
    reader = easyocr.Reader(['en'], gpu=False)
    print(f"EasyOCR Reader initialized in {time.time() - t0:.2f} seconds!")
except Exception as e:
    print(f"EasyOCR Reader initialization failed: {e}")
