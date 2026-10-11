import fitz

doc = fitz.open("d:/Desktop/AI PROJECT OCR MODEL/backend/uploads/MSME_PERSON_1.pdf")
text = ""
for page in doc:
    text += page.get_text()

with open("d:/Desktop/AI PROJECT OCR MODEL/backend/msme_text.txt", "w", encoding="utf-8") as f:
    f.write(text)

print("Saved msme text, length:", len(text))
