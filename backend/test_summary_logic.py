import re
from typing import List, Dict, Any

def parse_float_clean(val_str: str) -> float:
    if not val_str:
        return 0.0
    s = str(val_str).strip()
    s = re.sub(r'^(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|\€|\£|[\{\}\(\)\[\]\|]+)', '', s, flags=re.IGNORECASE).strip()
    s = re.sub(r'(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|\€|\£)$', '', s, flags=re.IGNORECASE).strip()
    s = re.sub(r'(\d)\s+(\d)', r'\1\2', s)

    if ',' in s and '.' not in s:
        if s.count(',') > 1:
            parts = s.split(',')
            if len(parts[-1]) == 2:
                s = "".join(parts[:-1]) + "." + parts[-1]
            else:
                s = "".join(parts)
        else:
            parts = s.split(',')
            if len(parts[-1]) == 2:
                s = parts[0] + "." + parts[1]
            elif len(parts[-1]) == 3:
                s = parts[0] + parts[1]
            else:
                s = s.replace(',', '.')
    elif ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')

    clean = re.sub(r'[^\d\.]', '', s)
    try:
        return float(clean)
    except ValueError:
        return 0.0

def detect_currency(text: str, regime: str = "auto") -> str:
    regime_lower = (regime or "auto").lower()

    # 1. Direct explicit currency symbols in the text ALWAYS take precedence
    if "$" in text:
        return "$"
    if "₹" in text:
        return "₹"
    if "€" in text:
        return "€"
    if "£" in text:
        return "£"

    # Explicit currency word codes in text
    if re.search(r'\b(?:USD|dollars?)\b', text, re.IGNORECASE):
        return "$"
    if re.search(r'\b(?:INR|Rs\.?|Rupees?)\b', text, re.IGNORECASE):
        return "₹"
    if re.search(r'\b(?:EUR|Euros?)\b', text, re.IGNORECASE):
        return "€"
    if re.search(r'\b(?:GBP|Pounds?)\b', text, re.IGNORECASE):
        return "£"

    # 2. Regional cues for India
    indian_cues = ["gstin", "cgst", "sgst", "igst", "hsn", "sac", "udyam", "msme", "maharashtra", "gujarat", "delhi", "karnataka", "tamil nadu", "bengaluru", "mumbai", "india", "pvt ltd", "private limited"]
    has_indian_cues = any(c in text.lower() for c in indian_cues)

    # 3. Regional cues for US ($)
    us_cues = ["united states", "usa", "ein", "social security", "federal tax", "sales tax"]
    has_us_cues = any(c in text.lower() for c in us_cues) or bool(
        re.search(r'\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)[;,\s]+\d{5}\b', text)
    ) or bool(re.search(r'\b\d{3}-\d{2}-\d{4}\b', text))

    # Check regime if not auto
    if regime_lower == "india" and (has_indian_cues or not has_us_cues):
        return "₹"
    elif regime_lower in ["us", "usa"] and (has_us_cues or not has_indian_cues):
        return "$"
    elif regime_lower in ["eu", "europe"]:
        return "€"
    elif regime_lower in ["uk", "gbp"]:
        return "£"

    # Auto detection from cues
    if has_indian_cues:
        return "₹"
    if has_us_cues:
        return "$"
    if "iban" in text.lower() or "vat" in text.lower():
        return "€"

    return "$"

def extract_financials(text: str, regime: str = "auto") -> Dict[str, Any]:
    curr = detect_currency(text, regime=regime)
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    amt_regex = r'(?:INR|\$|€|£|₹|Rs\.?)?\s*([0-9]{1,3}(?:[,\s][0-9]{3})*[\.,][0-9]{2}|[0-9]+[\.,][0-9]{2})'

    def find_amount(label_patterns: List[str]) -> float:
        for idx, line in enumerate(lines):
            for pat in label_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    # 1. Search in same line after label
                    tail = re.sub(pat, '', line, flags=re.IGNORECASE).strip()
                    amts = re.findall(amt_regex, tail, re.IGNORECASE)
                    if amts:
                        val = parse_float_clean(amts[-1])
                        if val > 0:
                            return val
                    # 2. Check next 1-4 lines for standalone amount
                    for next_idx in range(idx + 1, min(idx + 5, len(lines))):
                        next_line = lines[next_idx]
                        if any(re.search(lbl, next_line, re.IGNORECASE) for lbl in [
                            r"^(?:seller|client|buyer|billed to|ship to|items|terms|bank|payment\s*details|thank\s*you)",
                        ]):
                            break
                        amts_next = re.findall(amt_regex, next_line, re.IGNORECASE)
                        if amts_next:
                            val = parse_float_clean(amts_next[-1])
                            if val > 0:
                                return val
        return 0.0

    subtotal = find_amount([r"\bsub\s*total\b", r"\bsubtotal\b", r"\btaxable\s*value\b"])
    discount = find_amount([r"\btotal\s*discount\b", r"\bdiscount\b"])
    cgst = find_amount([r"\bcgst\b", r"\bcentral\s*gst\b"])
    sgst = find_amount([r"\bsgst\b", r"\bstate\s*gst\b"])
    igst = find_amount([r"\bigst\b", r"\bintegrated\s*gst\b"])
    other_taxes = find_amount([r"\bother\s*tax\b", r"\bsales\s*tax\b"])
    shipping = find_amount([r"\bshipping\b", r"\bfreight\b", r"\bdelivery\b"])
    grand_total = find_amount([r"\bgrand\s*total\b", r"\btotal\s*amount\b", r"^total[:\s]*[\$€£₹0-9]"])
    paid = find_amount([r"\bamount\s*paid\b", r"\bpaid\s*amount\b"])
    bal = find_amount([r"\bbalance\s*due\b", r"\boutstanding\b"])

    # Check for Summary / Net worth / Gross worth / VAT table blocks
    summary_idx = -1
    for i, line in enumerate(lines):
        if re.search(r'^(?:SUMMARY|TOTALS?|TAX\s*SUMMARY)\b', line, re.IGNORECASE):
            summary_idx = i
            break

    if summary_idx != -1:
        summary_lines = lines[summary_idx:]
        total_line_idx = -1
        for j, sline in enumerate(summary_lines):
            if re.match(r'^total\b', sline, re.IGNORECASE):
                total_line_idx = j
                break

        if total_line_idx != -1:
            amts_under_total = []
            for m in re.findall(amt_regex, summary_lines[total_line_idx]):
                v = parse_float_clean(m)
                if v > 0: amts_under_total.append(v)
            for next_idx in range(total_line_idx + 1, min(total_line_idx + 6, len(summary_lines))):
                for m in re.findall(amt_regex, summary_lines[next_idx]):
                    v = parse_float_clean(m)
                    if v > 0 and v not in amts_under_total:
                        amts_under_total.append(v)

            if len(amts_under_total) >= 3:
                if subtotal == 0.0:
                    subtotal = amts_under_total[0]
                if other_taxes == 0.0 and cgst == 0.0 and sgst == 0.0 and igst == 0.0:
                    other_taxes = amts_under_total[1]
                if grand_total == 0.0 or grand_total == subtotal:
                    grand_total = amts_under_total[2]
            elif len(amts_under_total) == 2:
                if subtotal == 0.0:
                    subtotal = min(amts_under_total)
                if grand_total == 0.0:
                    grand_total = max(amts_under_total)
                if other_taxes == 0.0:
                    other_taxes = round(grand_total - subtotal, 2)

    # Direct search for "Net worth" and "Gross worth" if still missing
    if subtotal == 0.0:
        subtotal = find_amount([r"\bnet\s*worth\b", r"\bnet\s*amount\b"])
    if grand_total == 0.0:
        grand_total = find_amount([r"\bgross\s*worth\b", r"\bgross\s*amount\b"])
    if other_taxes == 0.0 and (cgst + sgst + igst) == 0.0:
        other_taxes = find_amount([r"\bvat\b", r"\btax\b"])

    # Check for percentage tax (e.g. 10%)
    tax_rate_match = re.search(r'\b(\d{1,2}(?:\.\d{1,2})?)\s*%\b', text)
    if tax_rate_match and subtotal > 0.0:
        rate_pct = float(tax_rate_match.group(1))
        expected_tax = round(subtotal * (rate_pct / 100.0), 2)
        if other_taxes == 0.0 and (cgst + sgst + igst) == 0.0:
            if str(expected_tax) in text or f"{expected_tax:.2f}" in text or any(abs(parse_float_clean(m) - expected_tax) <= 0.05 for m in re.findall(amt_regex, text)):
                other_taxes = expected_tax

    # Mathematical reconciliation of Subtotal, Taxes, and Grand Total
    total_tax = cgst + sgst + igst + other_taxes
    calc_total = round(subtotal - discount + total_tax + shipping, 2)

    if subtotal > 0.0 and total_tax > 0.0:
        if grand_total == 0.0 or grand_total <= subtotal or abs(grand_total - calc_total) > 1.0:
            grand_total = calc_total

    if subtotal == 0.0 and grand_total > 0.0:
        if total_tax > 0.0:
            subtotal = max(0.0, round(grand_total - total_tax + discount - shipping, 2))
        else:
            subtotal = grand_total

    if grand_total == 0.0:
        if calc_total > 0.0:
            grand_total = calc_total
        else:
            numbers = re.findall(amt_regex, text)
            clean_nums = [parse_float_clean(n) for n in numbers]
            if clean_nums:
                grand_total = max(clean_nums)
                if subtotal == 0.0:
                    subtotal = grand_total

    if bal == 0.0 and grand_total > 0.0 and paid > 0 and paid < grand_total:
        bal = max(0.0, round(grand_total - paid, 2))

    return {
        "subtotal": subtotal,
        "total_discount": discount,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "igst_amount": igst,
        "other_taxes": other_taxes,
        "shipping_charges": shipping,
        "grand_total": grand_total,
        "currency": curr,
        "amount_paid": paid,
        "outstanding_balance": bal
    }

raw_ocr_text = """
Invoice no: 51109338
Date of issue:
04/13/2013
Seller:
Client:
Andrews, Kirby and Valdez
Becker Ltd
58861 Gonzalez Prairie
8012 Stewart Summit Apt: 455
Lake Daniellefurt; IN 57228
North Douglas, AZ 95355
Tax Id: 945-82-2137
Tax Id: 942-80-0517
IBAN: GBZSMCRLO6841367619257
ITEMS
No.
Description
Qty
UM
Net price
Net worth
VAT [%]
Gross
worth
CLEARANCE! Fast Dell Desktop
3,00
each
209,00
627,00
109
689,70
Computer PC DUAL CORE
WINDOWS 10 4/8/16GB RAM
HP T520 Thin Client Computer
5,00
each
37,75
188,75
10%
207,63
AMD GX-21ZJC 1.2GHz 4GB RAM
TESTED !READ BELOWI
gaming pc desktop computer
1,00
each
400,00
400,00
1090
440,00
12-Core Gaming Computer
3,00
each
464,89
394,67
109
534,14
Desktop PC Tower Affordable
GAMING PC 8GB AMD
RGB
Custom Build Dell Optiplex 9020
5,00
each
221,99
109,95
10%
220,95
MT i5-4570 3.ZOGHz Desktop
Computer PC
Dell Optiplex 990 MT Computer
each
269,95
079,80
10%
1 187,78
PC Quad Core i7 3.4GHz 16GB
2TB HD Windows 10 Pro
Dell Core
Duo Desktop
5,00
each
168,00
840,00
10%
924,00
Computer
Windows XP Pro
4GB
SOOGB
SUMMARY
VAT [P]
Net worth
VAT
Gross worth
10%
5 640,17
564,02
204,19
Total
5 640,17
564,02
204,19
Vega
"""

res = extract_financials(raw_ocr_text, regime="india")  # Even with regime="india" passed!
print("EXTRACTED RESULT WITH REGIME=INDIA:")
print(res)

res_auto = extract_financials(raw_ocr_text, regime="auto")
print("\nEXTRACTED RESULT WITH REGIME=AUTO:")
print(res_auto)
