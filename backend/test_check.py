import sys
import os

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    import fitz
    print("PyMuPDF (fitz): OK")
except Exception as e:
    print("PyMuPDF error:", e)

try:
    import cv2
    print("OpenCV: OK")
except Exception as e:
    print("OpenCV error:", e)

try:
    import pytesseract
    print("PyTesseract import: OK")
    tess_ver = pytesseract.get_tesseract_version()
    print("PyTesseract version:", tess_ver)
except Exception as e:
    print("PyTesseract error:", e)

try:
    import easyocr
    print("EasyOCR import: OK")
except Exception as e:
    print("EasyOCR error:", e)
