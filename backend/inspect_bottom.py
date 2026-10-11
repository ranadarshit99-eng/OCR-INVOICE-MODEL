import sys
sys.path.insert(0, 'd:/Desktop/AI PROJECT OCR MODEL/backend')
from ocr_engine import OCREngine

with open('d:/Desktop/AI PROJECT OCR MODEL/backend/uploads/batch1-0001.jpg', 'rb') as f:
    data = f.read()

ocr = OCREngine()
res = ocr.process_file(data, 'batch1-0001.jpg')
words = res.get('words_with_boxes', [])

print("--- WORDS NEAR BOTTOM ---")
for w in words:
    box = w.get('box', [])
    text = w.get('text', '')
    # If near bottom of image (say y > 0.7 * height or box[1] > 700)
    if box and box[1] > 800:
        print(f"y={box[1]}, x={box[0]}: '{text}'")
