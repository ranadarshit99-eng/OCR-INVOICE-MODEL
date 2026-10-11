import re

text = """INVOICE
BONCHAN CORPORATION
107 Strathmore Blvd.
Residential Home
TORONTO, Ontario, Canada
Invoice:112
Invoice date: FEB 13 2020
Due date: march 13 2020
Description
Qty
Price
Total
Low
Profile
SuperHighTack
1/2"
S102.00
S306
Glue
Dots
164"th
4000 roll
Torlscase
3M MPG12
Masking Paper
12"x6Oyds General
S152.00
S760
Purpose
12 /case
3M 201+
S14.00
S56
Masking Tape TAN
48mm
SSm 24
rolls/case
Araldite 2012
S215.00
S430
Epoxy
5Uml
cartridges box
120
cartridges case
Sub Total
1552
Shipping & Handing
50
Total Due
1602"""

label_patterns = [
    r"(?:Invoice\s*(?:No|Number|#|ID|Num)?[:#\-]+[ \t]*)([A-Z0-9\-\/]{1,30})",
    r"(?:Invoice\s*(?:No|Number|#|ID|Num)[ \t:\-]+)([A-Z0-9\-\/]{1,30})",
    r"(?:Tax\s*Invoice\s*(?:No|Number|#)?[:\s\-]+)([A-Z0-9\-\/]{1,30})",
    r"(?:Bill\s*(?:No|Number|#)?[:\s\-]+)([A-Z0-9\-\/]{1,30})",
    r"(?:INV[:\s\-]+)([A-Z0-9\-\/]{1,30})",
]

inv_num = ""
for p in label_patterns:
    m = re.search(p, text, re.IGNORECASE)
    if m:
        v = m.group(1).strip()
        if v.lower() not in ["seller", "vendor", "date", "number", "details", "client", "corporation"]:
            inv_num = v
            break

print("Extracted Invoice Num:", inv_num)

date_pattern = r"(?:\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b|\b\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\.]+\d{1,2}(?:st|nd|rd|th)?[\s,\-\.]+\d{2,4}\b|\b\d{1,2}(?:st|nd|rd|th)?[\s\-\.]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,\-\.]+\d{2,4}\b)"

m_inv = re.search(r"(?:Invoice\s*Date|Date\s*of\s*Issue|Date\s*Issued|Issue\s*Date|Billing\s*Date|Dated)[:\s\-\n]+(" + date_pattern + r")", text, re.IGNORECASE)
inv_date = m_inv.group(1).strip() if m_inv else ""

m_due = re.search(r"(?:Due\s*Date|Payment\s*Due|Pay\s*By|Valid\s*Till)[:\s\-\n]+(" + date_pattern + r")", text, re.IGNORECASE)
due_date = m_due.group(1).strip() if m_due else ""

print("Invoice Date:", inv_date)
print("Due Date:", due_date)
