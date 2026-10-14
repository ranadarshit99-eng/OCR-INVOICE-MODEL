import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("InvoiceExtractor")


def fix_gstin_ocr_typos(raw_str: str) -> str:
    """Fix common OCR character swaps in 15-character Indian GSTIN strings."""
    if not raw_str:
        return ""
    clean = re.sub(r'[^A-Za-z0-9]', '', raw_str).upper()
    if len(clean) != 15:
        return raw_str

    digit_positions = {0, 1, 7, 8, 9, 10, 14}
    letter_positions = {2, 3, 4, 5, 6, 11, 13}  # 12 is 'Z'

    char_list = list(clean)
    num_map = {'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1', 'Z': '7', 'S': '5', 'B': '8', 'G': '6', 'T': '7'}
    let_map = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B', '6': 'G', '7': 'T'}

    for idx in range(15):
        ch = char_list[idx]
        if idx in digit_positions:
            if ch in num_map:
                char_list[idx] = num_map[ch]
        elif idx in letter_positions:
            if ch in let_map:
                char_list[idx] = let_map[ch]
        elif idx == 12:
            if ch in {'2', 'Z', 'z'}:
                char_list[idx] = 'Z'

    return "".join(char_list)


def fix_ifsc_ocr_typos(raw_str: str) -> str:
    """Fix letter 'O' vs digit '0' in 11-char IFSC code (5th char must be '0')."""
    clean = re.sub(r'[^A-Za-z0-9]', '', raw_str).upper()
    if len(clean) == 11 and clean[:4].isalpha():
        char_list = list(clean)
        if char_list[4] == 'O':
            char_list[4] = '0'
        for i in range(5, 11):
            if char_list[i] == 'O':
                char_list[i] = '0'
        return "".join(char_list)
    return raw_str


def parse_float_clean(val_str: str) -> float:
    """Parse numeric currency strings handling OCR noise, European formats, and standard currency."""
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


def is_invalid_party_name(text: str) -> bool:
    """Strictly reject strings that are dates, document labels, totals, or metadata."""
    if not text or len(text.strip()) < 2:
        return True
    t = text.strip().lower()

    # Reject if text contains label markers or date keywords
    reject_keywords = [
        "date", "issue", "dated", "invoice", "receipt", "bill to", "billed to",
        "client:", "customer:", "vendor:", "seller:", "tax invoice", "tax", "vat",
        "gst", "gstin", "total", "subtotal", "amount", "balance", "due",
        "po box", "po number", "order", "items", "description", "qty",
        "quantity", "price", "rate", "tel:", "phone:", "fax:", "email:", "web:",
        "www.", "http", "@", "page 1", "terms", "condition", "thank you"
    ]
    if any(k in t for k in reject_keywords):
        return True

    # Reject if it's a date pattern (e.g. 04/13/2013 or 4/8/16)
    if re.search(r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b', text):
        return True

    # Reject if almost purely digits or punctuation
    alpha_count = sum(1 for c in text if c.isalpha())
    if alpha_count < 2 or (alpha_count / max(len(text), 1)) < 0.25:
        return True

    return False


class InvoiceExtractor:
    def __init__(self):
        pass

    def extract_invoice_number(self, text: str) -> str:
        label_patterns = [
            r"(?:Invoice\s*(?:No|Number|#|ID|Num)?[:#\-]+[ \t]*)([A-Z0-9\-\/]{2,30})",
            r"(?:Invoice\s*(?:No|Number|#|ID|Num)[ \t:\-]+)([A-Z0-9\-\/]{2,30})",
            r"(?:Tax\s*Invoice\s*(?:No|Number|#)?[:\s\-]+)([A-Z0-9\-\/]{2,30})",
            r"(?:Bill\s*(?:No|Number|#)?[:\s\-]+)([A-Z0-9\-\/]{2,30})",
            r"(?:INV[:\s\-]+)([A-Z0-9\-\/]{2,30})",
            r"(?:Invoice\s*#[:\s\-]*)([A-Z0-9\-\/]{2,30})"
        ]
        for p in label_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val.lower() not in ["seller", "vendor", "date", "number", "details", "client", "corporation", "ltd", "inc", "company"]:
                    prefix_match = re.search(r"\b(INV[\-\/]" + re.escape(val) + r")\b", text, re.IGNORECASE)
                    if prefix_match:
                        return prefix_match.group(1).strip()
                    return val

        m_fallback = re.search(r"\b(INV[\-\/][0-9A-Z\-\/]{3,20})\b", text, re.IGNORECASE)
        if m_fallback:
            return m_fallback.group(1).strip()

        return ""

    def extract_po_number(self, text: str) -> str:
        label_patterns = [
            r"(?:PO\s*(?:No|Number|#|Order)?[:\s\-]+)([A-Z0-9\-\/]{3,30})",
            r"(?:P\.O\.\s*No[:\s\-]+)([A-Z0-9\-\/]{3,30})",
            r"(?:Purchase\s*Order\s*No[:\s\-]+)([A-Z0-9\-\/]{3,30})",
        ]
        for p in label_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    def extract_dates(self, text: str) -> Dict[str, str]:
        # Support MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD, and Month Name dates like FEB 13 2020 or 13-Oct-2026
        date_pattern = r"(?:\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b|\b\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\.]+\d{1,2}(?:st|nd|rd|th)?[\s,\-\.]+\d{2,4}\b|\b\d{1,2}(?:st|nd|rd|th)?[\s\-\.]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,\-\.]+\d{2,4}\b)"

        inv_date = ""
        due_date = ""

        # Explicit Invoice Date search across single or multi-line
        m_inv = re.search(r"(?:Invoice\s*Date|Date\s*of\s*Issue|Date\s*Issued|Issue\s*Date|Billing\s*Date|Dated)[:\s\-\n]+(" + date_pattern + r")", text, re.IGNORECASE)
        if m_inv:
            inv_date = m_inv.group(1).strip()
        else:
            raw_dates = re.findall(date_pattern, text, re.IGNORECASE)
            clean_dates = []
            for d in raw_dates:
                # filter out hardware specs like 4/8/16
                if not re.search(r'(?:gb|ram|mb|core)', d, re.IGNORECASE):
                    parts = re.split(r'[\/\-\.\s]', d)
                    if len(parts) >= 3:
                        clean_dates.append(d)
            if clean_dates:
                inv_date = clean_dates[0].strip()

        # Explicit Due Date search - ONLY if labeled
        m_due = re.search(r"(?:Due\s*Date|Payment\s*Due|Pay\s*By|Valid\s*Till)[:\s\-\n]+(" + date_pattern + r")", text, re.IGNORECASE)
        if m_due:
            due_date = m_due.group(1).strip()

        return {"invoice_date": inv_date, "due_date": due_date}

    def extract_gstins(self, text: str) -> List[str]:
        raw_matches = re.findall(r"\b([0-9OQIZSBTG]{2}[A-Z0-9]{5}[0-9OQIZSBTG]{4}[A-Z]{1}[1-9A-Z]{1}[Z2][0-9A-Z]{1})\b", text, re.IGNORECASE)
        results = []
        for m in raw_matches:
            fixed = fix_gstin_ocr_typos(m)
            if fixed and fixed not in results:
                results.append(fixed)
        return results

    def extract_email(self, text: str) -> List[str]:
        clean_text = re.sub(r'(@[a-zA-Z0-9\-]+)\s+(com|in|org|net|co|io)\b', r'\1.\2', text)
        clean_text = re.sub(r'(@[a-zA-Z0-9\-]+?)(com|in|org|net|co|io)\b', r'\1.\2', clean_text)
        matches = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b", clean_text)
        results = []
        for m in matches:
            if m not in results:
                results.append(m)
        return results

    def extract_phone(self, text: str) -> List[str]:
        matches = re.findall(r"(?:Mob|Ph|Phone|Tel|Contact)[:\s\-]+(\+?[0-9\s\-]{8,15})", text, re.IGNORECASE)
        results = []
        for m in matches:
            clean_p = m.strip()
            if len(clean_p) >= 8 and clean_p not in results:
                results.append(clean_p)
        if not results:
            m_gen = re.findall(r"\b(\+91[\s\-][0-9]{5}[\s\-][0-9]{5})\b", text)
            for m in m_gen:
                if m not in results:
                    results.append(m)
        return results

    def extract_parties(self, text: str) -> Dict[str, Any]:
        """Extract vendor/seller and customer/buyer accurately without label contamination."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        gstins = self.extract_gstins(text)
        seller_gstin = gstins[0] if gstins else ""
        buyer_gstin = gstins[1] if len(gstins) > 1 else ""

        # International Tax IDs / VAT IDs / EIN
        tax_ids = re.findall(r"(?:Tax\s*Id|VAT\s*(?:No|Id|Number)?|EIN|TIN)[:\s\-]+([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if tax_ids:
            if not seller_gstin:
                seller_gstin = tax_ids[0]
            if len(tax_ids) > 1 and not buyer_gstin:
                buyer_gstin = tax_ids[1]

        phones = self.extract_phone(text)
        seller_phone = phones[0] if phones else ""

        emails = self.extract_email(text)
        seller_email = emails[0] if emails else ""

        seller_name = ""
        seller_address = ""
        buyer_name = ""
        buyer_address = ""

        # 1. Search for Buyer / Customer first (to prevent cross-contamination)
        for idx, line in enumerate(lines[:20]):
            if re.search(r"(?:billed to|bill to|customer|client|buyer|sold to)", line, re.IGNORECASE):
                # Clean same-line
                cand = re.sub(r"^.*?(?:billed to|bill to|customer|client|buyer|sold to)[:\s]*", "", line, flags=re.IGNORECASE).strip()
                cand = re.sub(r"^\(?customer\)?[:\s\-]*", "", cand, flags=re.IGNORECASE).strip()
                cand = re.sub(r"^\(?client\)?[:\s\-]*", "", cand, flags=re.IGNORECASE).strip()
                if len(cand) >= 3 and not is_invalid_party_name(cand) and not cand.startswith("(") and not any(k in cand.lower() for k in ["details", "invoice", "date", "phone", "gstin"]):
                    buyer_name = cand
                    break
                # Check next 2 lines
                for next_idx in range(idx + 1, min(idx + 3, len(lines))):
                    next_cand = lines[next_idx]
                    if not is_invalid_party_name(next_cand) and not any(k in next_cand.lower() for k in ["plot", "street", "road", "gstin", "invoice", "date", "phone", "details", "customer"]):
                        if len(next_cand) >= 3 and not re.search(r'\d{4,}', next_cand):
                            buyer_name = next_cand
                            break
                if buyer_name:
                    break

        # 2. Search for Seller / Vendor in top banner or under vendor label
        for idx, line in enumerate(lines[:12]):
            if re.search(r"^(?:seller|vendor|supplier|from)[:\s]*$", line, re.IGNORECASE) or "vendor details" in line.lower():
                for next_idx in range(idx + 1, min(idx + 4, len(lines))):
                    cand = lines[next_idx]
                    if not is_invalid_party_name(cand) and not any(k in cand.lower() for k in ["vendor", "seller", "details", "invoice", "date", "gstin", "phone", "email", "cyber", "street", "sector"]):
                        if len(cand) >= 3 and not re.search(r'\d{3,}', cand):
                            seller_name = cand
                            break
                if seller_name:
                    break

        # 3. Header Scan for Seller Company Banner (e.g. line 0)
        if not seller_name:
            for line in lines[:5]:
                if is_invalid_party_name(line):
                    continue
                if any(k in line.lower() for k in ["billed to", "bill to", "client", "customer", "details", "invoice", "receipt", "tax invoice"]):
                    continue
                clean_cand = re.sub(r'^(?:M\/s|Messrs\.?)\s+', '', line, flags=re.IGNORECASE).strip()
                if len(clean_cand) >= 4 and not re.search(r'\d{4,}', clean_cand):
                    seller_name = clean_cand
                    break

        # 4. Address keywords scan
        address_keywords = ["street", "st.", "road", "rd.", "avenue", "ave", "lane", "floor", "block", "sector", "suite", "city", "state", "pin", "zip", "box", "plaza", "building", "nagar", "marg", "plot", "complex", "cyber city"]
        
        # Seller Address Scan
        for line in lines[:15]:
            if line == seller_name or line == buyer_name or is_invalid_party_name(line):
                continue
            if any(k in line.lower() for k in ["billed to", "bill to", "customer", "invoice", "date", "total", "gstin", "phone", "email"]):
                continue
            if any(k in line.lower() for k in address_keywords) or ("," in line and sum(1 for c in line if c.isdigit()) >= 3):
                clean_line = re.sub(r'^(?:Address|Addr)[:\s\-]*', '', line, flags=re.IGNORECASE).strip()
                if clean_line:
                    seller_address = clean_line
                    break

        # Buyer Address Scan
        if buyer_name:
            for idx, line in enumerate(lines[:25]):
                if buyer_name.lower() in line.lower() and idx + 1 < len(lines):
                    for next_idx in range(idx + 1, min(idx + 3, len(lines))):
                        next_line = lines[next_idx]
                        if not is_invalid_party_name(next_line) and any(k in next_line.lower() for k in address_keywords):
                            buyer_address = next_line
                            break
                    if buyer_address:
                        break

        return {
            "seller_name": seller_name,
            "seller_address": seller_address,
            "seller_gstin": seller_gstin,
            "seller_phone": seller_phone,
            "seller_email": seller_email,
            "buyer_name": buyer_name,
            "buyer_address": buyer_address,
            "buyer_gstin": buyer_gstin,
            "billing_address": buyer_address,
            "shipping_address": buyer_address
        }

    def detect_currency(self, text: str, regime: str = "auto") -> str:
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
        if re.search(r'\b(?:USD|dollars?|CAD)\b', text, re.IGNORECASE):
            return "$"
        if re.search(r'\b(?:INR|Rs\.?|Rupees?)\b', text, re.IGNORECASE):
            return "₹"
        if re.search(r'\b(?:EUR|Euros?)\b', text, re.IGNORECASE):
            return "€"
        if re.search(r'\b(?:GBP|Pounds?)\b', text, re.IGNORECASE):
            return "£"

        # OCR artifact: $ often recognized as 'S' followed by digits and decimals
        if re.search(r'\bS\d+[\.,]\d{2}\b', text):
            return "$"

        # 2. Regional cues for India
        indian_cues = ["gstin", "cgst", "sgst", "igst", "hsn", "sac", "udyam", "msme", "maharashtra", "gujarat", "delhi", "karnataka", "tamil nadu", "bengaluru", "mumbai", "india", "pvt ltd", "private limited"]
        has_indian_cues = any(c in text.lower() for c in indian_cues)

        # 3. Regional cues for US / North America ($)
        us_cues = ["united states", "usa", "ein", "social security", "federal tax", "sales tax", "canada", "ontario", "toronto"]
        has_us_cues = any(c in text.lower() for c in us_cues) or bool(
            re.search(r'\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)[;,\s]+\d{5}\b', text)
        ) or bool(re.search(r'\b\d{3}-\d{2}-\d{4}\b', text))

        # Check regime if specified (only if document cues don't directly conflict)
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

    def extract_financials(self, text: str, regime: str = "auto") -> Dict[str, Any]:
        curr = self.detect_currency(text, regime=regime)
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        amt_regex = r'(?:INR|\$|€|£|₹|Rs\.?|S)?\s*([0-9]{1,3}(?:[,\s][0-9]{3})*[\.,][0-9]{2}|[0-9]+[\.,][0-9]{2})'

        tax_id_exclusions = [
            r"\btax\s*(?:id|identification|no|num|number|reg|registration|code|tin|payer|invoice)\b",
            r"\bvat\s*(?:id|identification|no|num|number|reg|registration|tin)\b",
            r"\bgst(?:in)?\s*(?:id|no|num|number)\b",
            r"\btaxable\b",
            r"\btotal\b",
            r"\bincl(?:uding)?\b"
        ]

        def find_amount(label_patterns: List[str], exclude_patterns: Optional[List[str]] = None, allow_int: bool = True) -> float:
            for idx, line in enumerate(lines):
                if exclude_patterns and any(re.search(ex, line, re.IGNORECASE) for ex in exclude_patterns):
                    continue
                for pat in label_patterns:
                    if re.search(pat, line, re.IGNORECASE):
                        # 1. Search in same line after label
                        tail = re.sub(pat, '', line, flags=re.IGNORECASE).strip()
                        # Scrub hyphenated IDs like 903-73-3743 or 930-75-1312 so digits aren't mistaken for currency
                        tail_clean = re.sub(r'\b\d{2,4}[-\/]\d{2,4}[-\/]\d{2,6}\b', '', tail)
                        tail_clean = re.sub(r'\b\d{3,}[-\/]\d{2,}\b', '', tail_clean)

                        amts = re.findall(amt_regex, tail_clean, re.IGNORECASE)
                        if amts:
                            val = parse_float_clean(amts[-1])
                            if val > 0:
                                return val

                        # Check whole number in same line tail (e.g. "Sub Total: 1552" or "Total Due: 1602")
                        if allow_int:
                            int_amts = re.findall(r'(?:INR|\$|€|£|₹|Rs\.?|S)\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,7})', tail_clean, re.IGNORECASE)
                            if not int_amts:
                                int_amts = re.findall(r'(?<![-\d\/])([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,7})(?![-\d\/])', tail_clean)
                            for ia in reversed(int_amts):
                                val = parse_float_clean(ia)
                                if val > 0 and val not in [1900, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027]:
                                    return val

                        # 2. Check next 1-4 lines for standalone amount
                        for next_idx in range(idx + 1, min(idx + 5, len(lines))):
                            next_line = lines[next_idx]
                            if any(re.search(lbl, next_line, re.IGNORECASE) for lbl in [
                                r"^(?:seller|client|buyer|billed to|ship to|items|terms|bank|payment\s*details|thank\s*you)",
                            ]):
                                break
                            if exclude_patterns and any(re.search(ex, next_line, re.IGNORECASE) for ex in exclude_patterns):
                                continue
                            next_line_clean = re.sub(r'\b\d{2,4}[-\/]\d{2,4}[-\/]\d{2,6}\b', '', next_line)
                            next_line_clean = re.sub(r'\b\d{3,}[-\/]\d{2,}\b', '', next_line_clean)
                            amts_next = re.findall(amt_regex, next_line_clean, re.IGNORECASE)
                            if amts_next:
                                val = parse_float_clean(amts_next[-1])
                                if val > 0:
                                    return val
                            if allow_int:
                                m_pure_num = re.search(r'^(?:INR|\$|€|£|₹|Rs\.?|S)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,7})\s*$', next_line_clean, re.IGNORECASE)
                                if m_pure_num:
                                    val = parse_float_clean(m_pure_num.group(1))
                                    if val > 0 and val not in [1900, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027]:
                                        return val
            return 0.0

        subtotal = find_amount([r"\bsub\s*total\b", r"\bsubtotal\b", r"\btaxable\s*value\b"])
        discount = find_amount([r"\btotal\s*discount\b", r"\bdiscount\b"])
        cgst = find_amount([r"\bcgst\b", r"\bcentral\s*gst\b"], exclude_patterns=tax_id_exclusions, allow_int=False)
        sgst = find_amount([r"\bsgst\b", r"\bstate\s*gst\b"], exclude_patterns=tax_id_exclusions, allow_int=False)
        igst = find_amount([r"\bigst\b", r"\bintegrated\s*gst\b"], exclude_patterns=tax_id_exclusions, allow_int=False)
        other_taxes = find_amount([r"\bother\s*tax\b", r"\bsales\s*tax\b"], exclude_patterns=tax_id_exclusions, allow_int=False)
        shipping = find_amount([r"\bshipping\b", r"\bfreight\b", r"\bdelivery\b", r"\bhanding\b", r"\bhandling\b"])
        grand_total = find_amount([
            r"\bgrand\s*total\b",
            r"\btotal\s*amount\b",
            r"\btotal\s*due\b",
            r"\bamount\s*due\b",
            r"\btotal\s*payable\b",
            r"\bbalance\s*due\b",
            r"\binvoice\s*total\b",
            r"^total[:\s]*[\$€£₹0-9S]",
            r"^total$"
        ])
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
            summary_amts = []
            for sline in summary_lines[1:min(14, len(summary_lines))]:
                if re.search(r'^(?:vat|net|gross|summary|items?|description)\b', sline, re.IGNORECASE):
                    continue
                # 1. OCR space-separated decimal like "55 57" -> 55.57
                m_space = re.findall(r'\b(\d{1,4})\s+(\d{2})\b', sline)
                for m1, m2 in m_space:
                    val = float(f"{m1}.{m2}")
                    if val > 0 and val not in summary_amts:
                        summary_amts.append(val)
                # 2. Standard decimal / comma numbers like "611.75" or "1447,00"
                m_nums = re.findall(amt_regex, sline)
                for mn in m_nums:
                    v = parse_float_clean(mn)
                    if v > 0 and v not in summary_amts:
                        summary_amts.append(v)

            if len(summary_amts) >= 3:
                gt = max(summary_amts)
                others = [x for x in summary_amts if x != gt]
                if len(others) >= 2:
                    tax_cand = min(others)
                    sub_cand = max(others)
                    if abs((sub_cand + tax_cand) - gt) <= 2.0:
                        if subtotal == 0.0: subtotal = sub_cand
                        if other_taxes == 0.0 and cgst == 0.0 and sgst == 0.0 and igst == 0.0: other_taxes = tax_cand
                        if grand_total == 0.0: grand_total = gt
                    else:
                        if subtotal == 0.0: subtotal = summary_amts[0]
                        if other_taxes == 0.0 and cgst == 0.0 and sgst == 0.0 and igst == 0.0: other_taxes = summary_amts[1]
                        if grand_total == 0.0: grand_total = summary_amts[2]
                else:
                    if grand_total == 0.0: grand_total = gt
            elif len(summary_amts) == 2:
                v_min, v_max = min(summary_amts), max(summary_amts)
                if other_taxes == 0.0 and cgst == 0.0 and sgst == 0.0 and igst == 0.0:
                    other_taxes = v_min
                if grand_total == 0.0:
                    grand_total = v_max
                if subtotal == 0.0:
                    subtotal = round(grand_total - other_taxes, 2)
            elif len(summary_amts) == 1:
                if grand_total == 0.0:
                    grand_total = summary_amts[0]

        # Direct search for "Net worth" and "Gross worth" if still missing (with OCR typo tolerance)
        if subtotal == 0.0:
            subtotal = find_amount([
                r"\bnet\s*worth\b", r"\bn[ec]t\s*wor[t\w]+\b",
                r"\bnet\s*amount\b", r"\bn[ec]t\s*amount\b"
            ])
        if grand_total == 0.0:
            grand_total = find_amount([
                r"\bgross\s*worth\b", r"\bgr[o0][s5ra]{1,3}\s*wor[t\w]+\b",
                r"\bgross\s*amount\b", r"\bgr[o0][s5ra]{1,3}\s*amount\b"
            ])
        if other_taxes == 0.0 and (cgst + sgst + igst) == 0.0:
            other_taxes = find_amount(
                [r"\bvat\s*(?:amt|amount|total)?\b", r"\btax\s*(?:amt|amount|total)\b", r"\bvat\b", r"\btax\s*\("],
                exclude_patterns=tax_id_exclusions,
                allow_int=False
            )

        # Sanity Guard: Tax can never equal or exceed Grand Total
        if grand_total > 0.0:
            if other_taxes >= grand_total:
                logger.warning(f"Sanity Check: Tax ({other_taxes}) >= Grand Total ({grand_total}). Setting tax to 0.0")
                other_taxes = 0.0
            if (cgst + sgst + igst) >= grand_total:
                logger.warning(f"Sanity Check: GST Taxes ({cgst + sgst + igst}) >= Grand Total ({grand_total}). Setting to 0.0")
                cgst, sgst, igst = 0.0, 0.0, 0.0

        # Check for percentage tax (e.g. 10%, 18%, 5%)
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

        if subtotal > 0.0 and (total_tax > 0.0 or shipping > 0.0):
            if grand_total == 0.0 or grand_total <= subtotal or abs(grand_total - calc_total) <= 1.0:
                grand_total = calc_total

        if subtotal == 0.0 and grand_total > 0.0:
            if total_tax > 0.0 and total_tax < grand_total:
                subtotal = max(0.0, round(grand_total - total_tax + discount - shipping, 2))
            else:
                subtotal = grand_total

        if grand_total == 0.0:
            if calc_total > 0.0:
                grand_total = calc_total
            else:
                clean_lines = [re.sub(r'\b\d{2,4}[-\/]\d{2,4}[-\/]\d{2,6}\b', '', l) for l in lines]
                numbers = re.findall(amt_regex, " ".join(clean_lines))
                clean_nums = [parse_float_clean(n) for n in numbers]
                if clean_nums:
                    grand_total = max(clean_nums)
                    if subtotal == 0.0:
                        subtotal = grand_total

        # Final sanity reconciliation: ensure tax never equals grand total and subtotal is populated
        total_tax = cgst + sgst + igst + other_taxes
        if grand_total > 0.0 and total_tax >= grand_total:
            other_taxes = 0.0
            total_tax = cgst + sgst + igst
            if total_tax >= grand_total:
                cgst, sgst, igst, total_tax = 0.0, 0.0, 0.0, 0.0
            if subtotal == 0.0 or subtotal >= grand_total:
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

    def extract_line_items(self, text: str, word_boxes: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        items = []
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        table_start_idx = 0
        table_end_idx = len(lines)

        for idx, line in enumerate(lines):
            line_low = line.lower()
            if any(k in line_low for k in ["item description", "description", "qty", "unit price", "hsn", "total (inr)"]):
                table_start_idx = idx + 1
            elif any(k in line_low for k in ["subtotal", "payment & bank", "grand total", "cgst", "terms & conditions"]):
                if idx > table_start_idx and table_start_idx > 0:
                    table_end_idx = idx
                    break

        table_lines = lines[table_start_idx:table_end_idx] if table_start_idx > 0 else lines

        # 1. First attempt: Single-line row matching
        i = 0
        while i < len(table_lines):
            line = table_lines[i]
            # Match: Description HSN Qty Price Total
            m_hsn = re.search(r"^(.+?)\s+(\d{4}|\d{6}|\d{8})\s+(\d+)\s+([A-Za-z0-9\.\,\s\{\}\$₹]+?)\s+([A-Za-z0-9\.\,\s\{\}\$₹]+)$", line)
            if m_hsn:
                desc = m_hsn.group(1).strip()
                hsn = m_hsn.group(2).strip()
                try:
                    qty = float(m_hsn.group(3))
                    price = parse_float_clean(m_hsn.group(4))
                    tot = parse_float_clean(m_hsn.group(5))
                    items.append({
                        "product_name": desc,
                        "product_description": desc,
                        "quantity": qty,
                        "unit_price": price,
                        "discount": 0.0,
                        "line_item_total": tot,
                        "hsn_sac_code": hsn
                    })
                    i += 1
                    continue
                except ValueError:
                    pass
            i += 1

        # 2. Second attempt: Clustered multi-line table matching (common in EasyOCR)
        if not items:
            clean_table_lines = [l for l in table_lines if not any(k in l.lower() for k in ["hsnisac", "unit price", "total (inr)", "oty", "item description"])]
            curr_desc = []
            curr_hsn = ""
            curr_prices = []

            for l in clean_table_lines:
                amt_match = re.search(r'(?:INR|\$|€|£|₹)?\s*([0-9]{1,3}(?:[,\s][0-9]{3})*(?:[\.,][0-9]{2})|[0-9]+(?:[\.,][0-9]{2}))', l, re.IGNORECASE)
                hsn_match = re.match(r'^(\d{4}|\d{6}|\d{8})$', l)

                if hsn_match and not curr_hsn:
                    curr_hsn = hsn_match.group(1)
                elif amt_match and ("INR" in l or "$" in l or "€" in l or "," in l or "." in l):
                    val = parse_float_clean(amt_match.group(1))
                    if val > 0:
                        curr_prices.append(val)
                        if len(curr_prices) == 2:
                            u_price, tot = curr_prices[0], curr_prices[1]
                            q = round(tot / u_price) if u_price > 0 else 1.0
                            name = " ".join(curr_desc) if curr_desc else "Service Item"
                            items.append({
                                "product_name": name,
                                "product_description": name,
                                "hsn_sac_code": curr_hsn or "9983",
                                "quantity": max(1.0, float(q)),
                                "unit_price": u_price,
                                "discount": 0.0,
                                "line_item_total": tot
                            })
                            curr_desc = []
                            curr_hsn = ""
                            curr_prices = []
                else:
                    if not any(k in l.lower() for k in ["subtotal", "cgst", "sgst", "total"]):
                        curr_desc.append(l)

        return items

    def extract_payment_details(self, text: str, fin: Dict[str, Any], regime: str = "auto") -> Dict[str, Any]:
        text_low = text.lower()

        method = ""
        if "upi" in text_low or "@" in text_low:
            method = "UPI / QR Code"
        elif "credit card" in text_low or "card" in text_low:
            method = "Credit/Debit Card"
        elif "bank transfer" in text_low or "wire" in text_low or "neft" in text_low or "rtgs" in text_low or "iban" in text_low:
            method = "Bank Transfer"
        elif "cash" in text_low:
            method = "Cash"
        elif "cheque" in text_low:
            method = "Cheque"

        terms = ""
        m_terms = re.search(r"(?:payment\s*terms|terms)[:\s]+([^\n]+)", text, re.IGNORECASE)
        if m_terms:
            terms = m_terms.group(1).strip()
        elif "net 30" in text_low:
            terms = "Net 30 Days"
        elif "net 15" in text_low:
            terms = "Net 15 Days"

        bank_name = ""
        m_bank = re.search(r"(?:Bank\s*Name|Banking\s*Partner)[:\s]+([^\n\r]+)", text, re.IGNORECASE)
        if m_bank:
            cand_b = m_bank.group(1).strip()
            cand_b = re.sub(r'[\s,]+(?:Account|A\/c|IFSC|Branch).*$', '', cand_b, flags=re.IGNORECASE).strip()
            if cand_b.lower() not in ["details", "name", "account", "bank"]:
                bank_name = cand_b

        acc_no = ""
        m_acc = re.search(r"(?:Account\s*No|A\/C\s*No|Acc\s*No)[:\s]+(\d{9,18})", text, re.IGNORECASE)
        if m_acc:
            acc_no = m_acc.group(1).strip()

        # IBAN extraction - ensure it's not confused with GSTIN
        iban = ""
        gstin_list = self.extract_gstins(text)
        m_iban = re.search(r"\bIBAN[:\s\-]*([A-Za-z0-9]+)\b", text, re.IGNORECASE)
        if m_iban:
            cand_ib = m_iban.group(1).strip()
            if cand_ib not in gstin_list:
                iban = cand_ib

        ifsc = ""
        m_ifsc = re.search(r"(?:IFSC\s*(?:Code)?[:\s\-]+)([A-Z]{4}[0O][A-Z0-9]{6})\b", text, re.IGNORECASE)
        if m_ifsc:
            cand_ifsc = fix_ifsc_ocr_typos(m_ifsc.group(1).strip().upper())
            if not any(w in cand_ifsc for w in ["CORP", "DECLAR", "ORGAN"]):
                ifsc = cand_ifsc
        elif ((regime and regime.lower() == "india") or len(gstin_list) > 0) and not any(c in text_low for c in ["canada", "toronto", "ontario", "usa"]):
            m_ifsc_gen = re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", text)
            if m_ifsc_gen:
                cand_ifsc = m_ifsc_gen.group(1).strip().upper()
                if not any(w in cand_ifsc for w in ["CORP", "DECLAR", "ORGAN"]):
                    ifsc = cand_ifsc

        upi_id = ""
        m_upi = re.search(r"(?:UPI\s*ID|UPI)[:\s]+([a-zA-Z0-9.\-_]+@[a-zA-Z]{2,64})", text, re.IGNORECASE)
        if m_upi:
            upi_id = m_upi.group(1).strip()

        gt = fin.get("grand_total", 0.0)
        paid = fin.get("amount_paid", 0.0)
        bal = fin.get("outstanding_balance", 0.0)

        status = ""
        if "unpaid" in text_low:
            status = "Unpaid"
        elif "paid" in text_low or (paid >= gt and gt > 0):
            status = "Paid"
        elif paid > 0 and bal > 0:
            status = "Partially Paid"

        po_ref = self.extract_po_number(text)

        return {
            "payment_method": method,
            "payment_terms": terms,
            "payment_status": status,
            "bank_account_details": {
                "bank_name": bank_name,
                "account_number": acc_no,
                "iban": iban,
                "ifsc_code": ifsc,
                "branch": "Main Branch" if bank_name else ""
            },
            "upi_id": upi_id,
            "transaction_reference_number": po_ref
        }

    def extract_dynamic_key_values(self, text: str) -> List[Dict[str, str]]:
        """Dynamically extract custom Key: Value pairs present on any document format."""
        pairs = []
        seen_keys = set()
        known_financial_keys = {
            "subtotal", "net worth", "total", "gross worth", "cgst", "sgst", "igst", "tax", "vat"
        }
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # 1. Single-line delimiter matching (Key: Value, Key - Value, Key = Value, Key | Value)
        for line in lines:
            m = re.match(r"^([A-Za-z0-9\s/.\-&#()]{2,40})[:\-=|]\s*([^\n\r]{2,120})$", line)
            if m:
                k = m.group(1).strip()
                v = m.group(2).strip()
                if not re.search(r'[A-Za-z]{2,}', k) or k[0].isdigit():
                    continue
                k_clean = re.sub(r'[\s_]+', ' ', k).title()
                if k.lower() not in known_financial_keys and k_clean not in seen_keys:
                    if not any(x in k.lower() for x in ["item description", "qty", "unit price", "hsn", "page"]):
                        seen_keys.add(k_clean)
                        pairs.append({"key": k_clean, "value": v})

        # 2. Multi-line label-value matching (Line i is label, Line i+1 is value)
        key_indicators = [
            "name of enterprise", "enterprise name", "type of enterprise", "type of organisation",
            "type of organization", "date of incorporation", "date of filing", "date of printing",
            "date of issue", "official address of enterprise", "official address", "registered office",
            "activity type", "activity description", "activity / description", "nic 2 digit", "nic 4 digit",
            "reference no", "registration no", "registration / reference no", "enrollment no",
            "certificate no", "roll no", "subject", "course", "department", "semester",
            "customer name", "client name", "account holder", "branch name", "pan", "tan", "cin",
            "mobile", "contact", "email", "website", "order id", "tracking id", "ship to", "bill to"
        ]

        for i in range(len(lines) - 1):
            line_low = lines[i].lower().strip().rstrip(':').rstrip('-')
            if any(line_low == ki or line_low.startswith(ki) for ki in key_indicators):
                k_title = lines[i].strip().rstrip(':').rstrip('-').title()
                if k_title not in seen_keys:
                    val = lines[i + 1].strip()
                    if val and not any(val.lower() == ki for ki in key_indicators) and len(val) >= 2:
                        seen_keys.add(k_title)
                        pairs.append({"key": k_title, "value": val})

        # 3. Reference / Identification Numbers anywhere in the document
        ref_patterns = [
            (r"\b([A-Z]{2}-\d{2}-\d{5,10})\b", "State Registration Code"),
            (r"\b(UDYAM-[A-Z]{2}-\d{2}-\d{7})\b", "Udyam Registration Number"),
            (r"\b([A-Z]{5}\d{4}[A-Z]{1})\b", "Permanent Account Number (PAN)"),
            (r"\b([LUu]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b", "Corporate Identity Number (CIN)"),
            (r"\b(REF[:\s\-#]+[A-Z0-9\-\/]{4,25})\b", "Document Reference Number"),
            (r"\b(PO[:\s\-#]+[A-Z0-9\-\/]{4,25})\b", "Purchase Order Code"),
        ]
        for pat, label in ref_patterns:
            if label not in seen_keys:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    code_val = m.group(1).strip()
                    seen_keys.add(label)
                    pairs.append({"key": label, "value": code_val})

        return pairs[:30]

    def build_detected_fields(self, extracted: Dict[str, Any], dynamic_pairs: List[Dict[str, str]] = None, raw_text: str = "") -> List[Dict[str, Any]]:
        """
        Build the list of ONLY genuine fields actually found in this document.
        Adapts gracefully to both commercial invoices and general document formats.
        """
        detected = []
        seen_labels = set()

        basic = extracted.get("basic_details", {})
        seller = extracted.get("seller_details", {})
        buyer = extracted.get("buyer_details", {})
        fin = extracted.get("financial_details", {})
        pay = extracted.get("payment_details", {})
        bank = pay.get("bank_account_details", {}) if pay else {}
        items = extracted.get("line_items", [])

        def add_if_present(field_id: str, label: str, value: Any, category: str, conf: int = 94, is_stat: bool = True):
            if value is not None and str(value).strip() != "" and str(value).strip() != "0.0" and str(value).strip() != "0":
                val_str = str(value).strip()
                if label not in seen_labels:
                    seen_labels.add(label)
                    detected.append({
                        "id": field_id,
                        "label": label,
                        "value": val_str,
                        "category": category,
                        "confidence": conf,
                        "is_statutory": is_stat
                    })

        # Category A: Basic Details
        add_if_present("invoice_number", "Document / Invoice Number", basic.get("invoice_number"), "Basic Details", 96)
        add_if_present("invoice_date", "Document Date", basic.get("invoice_date"), "Basic Details", 95)
        add_if_present("due_date", "Due Date", basic.get("due_date"), "Basic Details", 90)
        add_if_present("invoice_type", "Document Classification", basic.get("invoice_type"), "Basic Details", 92)
        add_if_present("purchase_order_number", "PO / Order Number", basic.get("purchase_order_number"), "Basic Details", 88)

        # Category B: Seller Details / Issuing Entity
        add_if_present("seller_name", "Issuing Entity / Organization", seller.get("seller_name"), "Entity Details", 94)
        add_if_present("seller_gstin", "Tax ID / VAT / GSTIN", seller.get("seller_gstin"), "Entity Details", 96)
        add_if_present("seller_address", "Official Address", seller.get("seller_address"), "Entity Details", 89)
        add_if_present("seller_phone", "Contact Phone", seller.get("seller_phone"), "Entity Details", 92)
        add_if_present("seller_email", "Email Address", seller.get("seller_email"), "Entity Details", 95)

        # Category C: Buyer Details / Recipient
        add_if_present("buyer_name", "Recipient / Client Name", buyer.get("buyer_name"), "Recipient Details", 93)
        add_if_present("buyer_gstin", "Recipient Tax ID / VAT", buyer.get("buyer_gstin"), "Recipient Details", 95)
        add_if_present("buyer_address", "Recipient Address", buyer.get("buyer_address"), "Recipient Details", 88)

        # Category D & E: Financials (Only if genuinely present)
        curr = fin.get("currency", "$")
        if fin.get("subtotal", 0.0) > 0:
            add_if_present("subtotal", "Subtotal (Net Amount)", f"{curr} {fin.get('subtotal', 0.0):,.2f}", "Financials", 96)
        if fin.get("total_discount", 0.0) > 0:
            add_if_present("total_discount", "Discount", f"{curr} {fin.get('total_discount', 0.0):,.2f}", "Financials", 92)
        if fin.get("cgst_amount", 0.0) > 0:
            add_if_present("cgst_amount", "CGST Amount", f"{curr} {fin.get('cgst_amount', 0.0):,.2f}", "Financials", 93)
        if fin.get("sgst_amount", 0.0) > 0:
            add_if_present("sgst_amount", "SGST Amount", f"{curr} {fin.get('sgst_amount', 0.0):,.2f}", "Financials", 93)
        if fin.get("igst_amount", 0.0) > 0:
            add_if_present("igst_amount", "IGST Amount", f"{curr} {fin.get('igst_amount', 0.0):,.2f}", "Financials", 93)
        if fin.get("other_taxes", 0.0) > 0:
            add_if_present("other_taxes", "Tax / VAT Amount", f"{curr} {fin.get('other_taxes', 0.0):,.2f}", "Financials", 94)
        if fin.get("shipping_charges", 0.0) > 0:
            add_if_present("shipping_charges", "Shipping & Freight", f"{curr} {fin.get('shipping_charges', 0.0):,.2f}", "Financials", 91)
        if fin.get("grand_total", 0.0) > 0:
            add_if_present("grand_total", "Grand Total (Gross Amount)", f"{curr} {fin.get('grand_total', 0.0):,.2f}", "Financials", 98)

        # Category F: Payment Details
        add_if_present("payment_method", "Payment Method", pay.get("payment_method"), "Payment Details", 88)
        add_if_present("payment_status", "Payment Status", pay.get("payment_status"), "Payment Details", 89)
        add_if_present("bank_name", "Bank Name", bank.get("bank_name"), "Payment Details", 90)
        add_if_present("account_number", "Bank Account Number", bank.get("account_number"), "Payment Details", 94)
        add_if_present("iban", "IBAN / Bank Routing", bank.get("iban"), "Payment Details", 95)
        add_if_present("ifsc_code", "IFSC Code", bank.get("ifsc_code"), "Payment Details", 93)
        add_if_present("upi_id", "UPI ID", pay.get("upi_id"), "Payment Details", 92)

        # Line Items Summary
        if items:
            add_if_present("line_items_count", "Line Items Extracted", f"{len(items)} items detected", "Line Items", 95, False)

        # Dynamic Document Fields
        if dynamic_pairs:
            for pair in dynamic_pairs:
                add_if_present(f"dyn_{pair['key'].lower().replace(' ', '_')}", pair['key'], pair['value'], "Document Custom Keys", 88, False)

        # Universal Fallback: If document produced few fields (e.g. general document, form, report)
        if len(detected) < 6 and raw_text:
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            # Extract prominent banner / title
            if len(lines) > 0 and "Document Header / Title" not in seen_labels:
                header_line = lines[0]
                if len(header_line) >= 3 and len(header_line) <= 80:
                    add_if_present("doc_header", "Document Header / Title", header_line, "Document Content", 92, False)
            if len(lines) > 1 and "Issuing Sub-Header" not in seen_labels:
                sub_header = lines[1]
                if len(sub_header) >= 3 and len(sub_header) <= 80:
                    add_if_present("doc_subheader", "Issuing Sub-Header", sub_header, "Document Content", 90, False)
            # Extract salient text statements
            statement_idx = 1
            for l in lines[2:15]:
                if len(l) >= 8 and len(l) <= 90 and not any(k in l.lower() for k in ["page", "copyright", "confidential", "valid"]):
                    add_if_present(f"doc_statement_{statement_idx}", f"Statement #{statement_idx}", l, "Document Content", 86, False)
                    statement_idx += 1
                    if len(detected) >= 12:
                        break

        return detected

    def process(self, ocr_data: Dict[str, Any], regime: str = "auto") -> Dict[str, Any]:
        text = ocr_data.get("text", "")
        word_boxes = ocr_data.get("words_with_boxes", [])

        inv_num = self.extract_invoice_number(text)
        po_num = self.extract_po_number(text)
        dates = self.extract_dates(text)

        inv_type = "Tax Invoice" if "tax invoice" in text.lower() else ("Commercial Invoice" if "commercial invoice" in text.lower() else "Invoice")

        parties = self.extract_parties(text)
        financials = self.extract_financials(text, regime=regime)
        line_items = self.extract_line_items(text, word_boxes)
        payment = self.extract_payment_details(text, financials, regime=regime)
        dyn_pairs = self.extract_dynamic_key_values(text)

        extracted = {
            "basic_details": {
                "invoice_number": inv_num,
                "invoice_date": dates["invoice_date"],
                "due_date": dates["due_date"],
                "invoice_type": inv_type,
                "purchase_order_number": po_num
            },
            "seller_details": {
                "seller_name": parties["seller_name"],
                "seller_address": parties["seller_address"],
                "seller_gstin": parties["seller_gstin"],
                "seller_phone": parties["seller_phone"],
                "seller_email": parties["seller_email"]
            },
            "buyer_details": {
                "buyer_name": parties["buyer_name"],
                "buyer_address": parties["buyer_address"],
                "buyer_gstin": parties["buyer_gstin"],
                "billing_address": parties["billing_address"],
                "shipping_address": parties["shipping_address"]
            },
            "line_items": line_items,
            "financial_details": financials,
            "payment_details": payment,
            "dynamic_pairs": dyn_pairs
        }

        extracted["detected_fields"] = self.build_detected_fields(extracted, dyn_pairs)
        return extracted
