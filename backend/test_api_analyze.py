import urllib.request
import json
import mimetypes

url = "http://127.0.0.1:8005/api/analyze"
filepath = "d:/Desktop/AI PROJECT OCR MODEL/backend/uploads/batch1-0001.jpg"

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
with open(filepath, 'rb') as f:
    file_bytes = f.read()

import sys
sys.stdout.reconfigure(encoding='utf-8')

body = []
body.append(f'--{boundary}'.encode())
body.append(b'Content-Disposition: form-data; name="regime"')
body.append(b'\r\nauto')
body.append(f'--{boundary}'.encode())
body.append(b'Content-Disposition: form-data; name="file"; filename="batch1-0001.jpg"')
body.append(b'Content-Type: image/jpeg\r\n')
body.append(file_bytes)
body.append(f'--{boundary}--'.encode())
body.append(b'')

data = b'\r\n'.join(body)

req = urllib.request.Request(url, data=data)
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

resp = urllib.request.urlopen(req)
res_json = json.loads(resp.read().decode())

print("=== API ANALYZE RESULT FOR batch1-0001.jpg ===")
fin = res_json.get("extracted_data", {}).get("financial_details", {})
print("Financial details:", fin)
print("\nDetected fields for Financials:")
for df in res_json.get("detected_fields", []):
    if df.get("category") == "Financials":
        print(f"  {df['label']}: {df['value']}")

math_res = res_json.get("verification", {}).get("total_amount_validation", {})
print("\nMath Verification:", math_res)
