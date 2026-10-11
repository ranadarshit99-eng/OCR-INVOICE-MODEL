import os
import pytesseract

possible_paths = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
]

found = None
for p in possible_paths:
    if os.path.exists(p):
        found = p
        break

print("Tesseract binary found at:", found)
if found:
    pytesseract.pytesseract.tesseract_cmd = found
    try:
        print("Tesseract version:", pytesseract.get_tesseract_version())
    except Exception as e:
        print("Tesseract error:", e)
