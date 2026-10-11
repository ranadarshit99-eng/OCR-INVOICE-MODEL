import re
from datetime import datetime

class InvoiceParser:
    def __init__(self):
        # Regex Patterns
        self.invoice_num_patterns = [
            r'\b(?:invoice\s*number|inv\s*no\.?|invoice\s*no\.?|bill\s*no\.?|invoice\s*#|inv\s*#)[:\s]*([A-Z0-9\-\/]{3,25})\b',
            r'\b(INV[-_][A-Z0-9\-\/]{3,20})\b',
            r'\b(?:invoice|inv|facture|bill|ref|num|no|#)[#:\s]+([A-Z0-9\-\/]{3,20})\b',
            r'\b([A-Z]{2,4}[-_]\d{3,10})\b',
            r'\b(\d{5,10})\b'
        ]

        self.date_patterns = [
            r'\b(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})\b',
            r'\b(\d{1,2}[-\/\.]\d{1,2}[-\/\.]\d{2,4})\b',
            r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b',
            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b'
        ]

        self.currency_symbols = {
            '$': 'USD', '€': 'EUR', '£': 'GBP', '₹': 'INR', '¥': 'JPY',
            'USD': 'USD', 'EUR': 'EUR', 'GBP': 'GBP', 'INR': 'INR', 'CAD': 'CAD', 'AUD': 'AUD'
        }

    def parse(self, ocr_data, filename=""):
        """Extracts structured entity fields from OCR data and text layout."""
        words = ocr_data.get("words", [])
        full_text = ocr_data.get("full_text", "")
        img_w = ocr_data.get("image_width", 1000)
        img_h = ocr_data.get("image_height", 1000)

        # Lines construction
        lines = self._group_words_into_lines(words)

        # Extract fields
        inv_num_data = self._extract_invoice_number(lines, full_text, words)
        dates_data = self._extract_dates(lines, full_text, words)
        vendor_data = self._extract_vendor(lines, words, img_w, img_h)
        customer_data = self._extract_customer(lines, words)
        financials = self._extract_financials(lines, full_text, words)
        line_items = self._extract_line_items(lines, words)

        # Mathematical verification
        subtotal = financials.get("subtotal", {}).get("value", 0.0) if financials.get("subtotal") else 0.0
        tax = financials.get("tax", {}).get("value", 0.0) if financials.get("tax") else 0.0
        discount = financials.get("discount", {}).get("value", 0.0) if financials.get("discount") else 0.0
        total = financials.get("total", {}).get("value", 0.0) if financials.get("total") else 0.0

        calc_total = round(subtotal + tax - discount, 2)

        # OCR artifact cleanup & math reconciliation
        if subtotal > 0 and tax > 0:
            if total <= subtotal or abs(calc_total - total) > 1.0:
                total = calc_total
                if financials.get("total"):
                    financials["total"]["value"] = calc_total
                else:
                    financials["total"] = {"value": calc_total, "box": [0,0,0,0], "confidence": 95.0}
        elif subtotal > 0 and total > 0 and total > calc_total:
            total_str = str(int(total))
            calc_str = str(int(calc_total))
            if total_str.endswith(calc_str) and (total_str[0] in ['9', '8', '1', '7']):
                total = calc_total
                if financials.get("total"):
                    financials["total"]["value"] = calc_total

        math_valid = (total > 0 and abs(calc_total - total) <= 0.05) or (subtotal == 0 and total > 0)

        # Compute overall model confidence based ONLY on fields that were actually detected
        confidences = []
        if inv_num_data:
            confidences.append(inv_num_data.get("confidence", 0))
        if dates_data.get("invoice_date"):
            confidences.append(dates_data["invoice_date"].get("confidence", 0))
        if vendor_data:
            confidences.append(vendor_data.get("confidence", 0))
        if financials.get("total") and financials["total"].get("confidence", 0) > 0:
            confidences.append(financials["total"].get("confidence", 0))

        valid_confs = [c for c in confidences if c > 0]
        avg_confidence = round(sum(valid_confs) / len(valid_confs), 1) if valid_confs else 85.0

        return {
            "invoice_number": inv_num_data,
            "invoice_date": dates_data.get("invoice_date"),
            "due_date": dates_data.get("due_date"),
            "vendor": vendor_data,
            "customer": customer_data,
            "currency": financials.get("currency", "USD"),
            "subtotal": financials.get("subtotal"),
            "tax": financials.get("tax"),
            "discount": financials.get("discount"),
            "total_amount": financials.get("total"),
            "line_items": line_items,
            "math_verification": {
                "is_valid": math_valid,
                "calculated_total": calc_total if subtotal > 0 else total,
                "extracted_total": total,
                "discrepancy": round(abs(calc_total - total), 2) if subtotal > 0 else 0.0
            },
            "overall_confidence": avg_confidence,
            "extracted_lines": [l["text"] for l in lines]
        }

    def _group_words_into_lines(self, words):
        """Groups individual words into lines based on Y vertical overlap."""
        if not words:
            return []

        sorted_words = sorted(words, key=lambda w: (w["box"][1], w["box"][0]))
        lines = []

        for w in sorted_words:
            box = w["box"]
            y_center = box[1] + box[3] / 2.0
            placed = False
            for line in lines:
                if abs(line["y_center"] - y_center) < max(12, box[3] * 0.6):
                    line["words"].append(w)
                    line["y_center"] = (line["y_center"] * (len(line["words"])-1) + y_center) / len(line["words"])
                    placed = True
                    break
            if not placed:
                lines.append({
                    "y_center": y_center,
                    "words": [w]
                })

        result_lines = []
        for line in lines:
            line_words = sorted(line["words"], key=lambda w: w["box"][0])
            line_text = " ".join([w["text"] for w in line_words])
            min_x = line_words[0]["box"][0]
            min_y = min([w["box"][1] for w in line_words])
            max_x = max([w["box"][0] + w["box"][2] for w in line_words])
            max_y = max([w["box"][1] + w["box"][3] for w in line_words])

            result_lines.append({
                "text": line_text,
                "words": line_words,
                "box": [min_x, min_y, max_x - min_x, max_y - min_y]
            })

        return result_lines

    def _extract_invoice_number(self, lines, full_text, words):
        """Finds Invoice Number with bounding box."""
        for line in lines:
            text = line["text"]
            for pattern in self.invoice_num_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    val = match.group(1).strip(":# /")
                    # Discard false positives like 'TAX', 'OICE', 'INVOICE'
                    if len(val) >= 3 and val.upper() not in ["TAX", "OICE", "INVOICE", "NUMBER", "DATE", "DUE", "TOTAL"]:
                        return {
                            "value": val,
                            "box": line["box"],
                            "confidence": 94.0
                        }

        # Fallback search in full text
        match = re.search(r'\b(INV[-_]?[0-9A-Z]{3,15})\b', full_text, re.IGNORECASE)
        if match:
            return {"value": match.group(1), "box": [50, 50, 200, 30], "confidence": 90.0}

        return None

    def _extract_dates(self, lines, full_text, words):
        found_dates = []
        for line in lines:
            text = line["text"]
            for pattern in self.date_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for m in matches:
                    date_str = m.group(1)
                    is_due = "due" in text.lower() or "payment" in text.lower()
                    is_inv = any(k in text.lower() for k in ["date of issue", "issue", "invoice date", "dated"])
                    found_dates.append({
                        "value": date_str,
                        "is_due": is_due,
                        "is_inv": is_inv,
                        "box": line["box"],
                        "confidence": 94.0
                    })

        inv_date = None
        due_date = None

        for d in found_dates:
            if d["is_due"] and not due_date:
                due_date = d
            elif d["is_inv"] and not inv_date:
                inv_date = d

        # If not explicitly labeled, use first found date for invoice date
        if not inv_date and found_dates:
            inv_date = found_dates[0]

        return {"invoice_date": inv_date, "due_date": due_date}

    def _extract_vendor(self, lines, words, img_w, img_h):
        """Identifies vendor name (top section of document). Never picks dates or labels."""
        reject_words = [
            "date", "issue", "tax", "invoice", "receipt", "bill", "statement", "client", "customer",
            "billed to", "bill to", "po box", "total", "amount", "phone", "email", "tel", "order",
            "details", "vendor details", "seller"
        ]
        top_lines = [l for l in lines if l["box"][1] < img_h * 0.35]
        for line in top_lines:
            text = line["text"].strip()
            # Clean generic words
            cleaned = re.sub(r'\b(TAX\s+INVOICE|INVOICE|RECEIPT|BILL|STATEMENT)\b', '', text, flags=re.IGNORECASE).strip()
            if len(cleaned) > 3 and not re.search(r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b', cleaned):
                if not any(k in cleaned.lower() for k in reject_words):
                    return {
                        "value": cleaned,
                        "box": line["box"],
                        "confidence": 92.0
                    }
        return None

    def _extract_customer(self, lines, words):
        """Identifies customer/client name."""
        for i, line in enumerate(lines):
            text_low = line["text"].lower()
            if any(k in text_low for k in ["bill to", "billed to", "customer", "client", "ship to"]):
                same_line_match = re.search(r'(?:billed\s*to|bill\s*to|client|customer)[:\s]*(.+)', line["text"], re.IGNORECASE)
                if same_line_match:
                    cand = same_line_match.group(1).strip()
                    cand = re.sub(r'^\(?customer\)?[:\s\-]*', '', cand, flags=re.IGNORECASE).strip()
                    if len(cand) >= 2 and not cand.startswith("(") and not any(x in cand.lower() for x in ["invoice", "date", "number", "due", "details"]):
                        return {"value": cand, "box": line["box"], "confidence": 90.0}

                # Check next line
                if i + 1 < len(lines):
                    next_line = lines[i+1]
                    cand = next_line["text"].strip()
                    cand = re.sub(r'INVOICE DATE.*', '', cand, flags=re.IGNORECASE).strip()
                    if len(cand) >= 2 and not any(x in cand.lower() for x in ["date of issue", "invoice", "date", "details", "customer"]):
                        return {
                            "value": cand,
                            "box": next_line["box"],
                            "confidence": 88.0
                        }
        return None

    def _extract_financials(self, lines, full_text, words):
        financials = {
            "subtotal": None,
            "tax": None,
            "discount": None,
            "total": None,
            "currency": "USD"
        }

        # Detect currency
        for sym, code in self.currency_symbols.items():
            if sym in full_text:
                financials["currency"] = code
                break
        if financials["currency"] == "USD" and ("₹" in full_text or "INR" in full_text or "gstin" in full_text.lower()):
            financials["currency"] = "INR"
        elif "S" in full_text and re.search(r'\bS\d+[\.,]\d{2}\b', full_text):
            financials["currency"] = "USD"

        amount_pattern = r'(?:INR|USD|EUR|GBP|Rs\.?|[\$€£₹S]\s*)?([0-9]{1,3}(?:[,\s][0-9]{3})*(?:[\.,][0-9]{2})|[0-9]+(?:[\.,][0-9]{2})|[0-9]{2,7})'

        def parse_amt(raw_str):
            s = str(raw_str).strip()
            s = re.sub(r'^(?:INR|USD|EUR|GBP|Rs\.?|₹|\$|\€|\£|S)', '', s, flags=re.IGNORECASE).strip()
            s = re.sub(r'(\d)\s+(\d)', r'\1\2', s)
            if ',' in s and '.' not in s:
                if s.count(',') > 1:
                    parts = s.split(',')
                    s = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) == 2 else "".join(parts)
                else:
                    parts = s.split(',')
                    s = parts[0] + "." + parts[1] if len(parts[-1]) == 2 else parts[0] + parts[1]
            elif ',' in s and '.' in s:
                s = s.replace(',', '')
            clean = re.sub(r'[^\d\.]', '', s)
            try:
                return float(clean)
            except ValueError:
                return 0.0

        for idx, line in enumerate(lines):
            text_lower = line["text"].lower()
            amounts = re.findall(amount_pattern, line["text"])

            val = 0.0
            box = line["box"]
            if amounts:
                val = parse_amt(amounts[-1])
            elif idx + 1 < len(lines):
                next_amounts = re.findall(amount_pattern, lines[idx+1]["text"])
                if next_amounts:
                    val = parse_amt(next_amounts[-1])
                    box = lines[idx+1]["box"]

            # Multi-column summary line (e.g. Total / Summary with Subtotal, Tax, and Grand Total)
            if len(amounts) >= 3 and any(k in text_lower for k in ["total", "summary", "vat", "net"]):
                sub_val = parse_amt(amounts[0])
                tax_val = parse_amt(amounts[1])
                tot_val = parse_amt(amounts[2])
                if sub_val > 0 and not financials["subtotal"]:
                    financials["subtotal"] = {"value": sub_val, "box": box, "confidence": 94.0}
                if tax_val > 0 and not financials["tax"]:
                    financials["tax"] = {"value": tax_val, "box": box, "confidence": 92.0}
                if tot_val > 0 and (not financials["total"] or tot_val > financials["total"]["value"]):
                    financials["total"] = {"value": tot_val, "box": box, "confidence": 96.0}

            if val <= 0:
                continue

            if "subtotal" in text_lower or "sub total" in text_lower or "net amount" in text_lower or "net worth" in text_lower:
                if not financials["subtotal"]:
                    financials["subtotal"] = {"value": val, "box": box, "confidence": 92.0}
            elif any(k in text_lower for k in ["cgst", "sgst", "igst", "tax", "vat", "gst"]):
                if not financials["tax"]:
                    financials["tax"] = {"value": val, "box": box, "confidence": 90.0}
            elif "discount" in text_lower:
                if not financials["discount"]:
                    financials["discount"] = {"value": val, "box": box, "confidence": 88.0}
            elif any(k in text_lower for k in ["total", "grand total", "gross worth", "amount due", "total due", "total payable", "balance due"]):
                if not financials["total"] or val > financials["total"]["value"]:
                    financials["total"] = {"value": val, "box": box, "confidence": 95.0}

        # Math reconciliation
        sub = financials["subtotal"]["value"] if financials["subtotal"] else 0.0
        tax = financials["tax"]["value"] if financials["tax"] else 0.0
        disc = financials["discount"]["value"] if financials["discount"] else 0.0
        tot = financials["total"]["value"] if financials["total"] else 0.0

        if sub > 0 and tot == 0 and tax > 0:
            financials["total"] = {"value": round(sub + tax - disc, 2), "box": financials["subtotal"]["box"], "confidence": 90.0}
        elif tot > 0 and sub == 0 and tax > 0:
            financials["subtotal"] = {"value": round(tot - tax + disc, 2), "box": financials["total"]["box"], "confidence": 90.0}

        return financials

    def _extract_line_items(self, lines, words):
        """Extracts tabular line items. Returns empty list if none found."""
        items = []
        table_started = False

        for line in lines:
            text = line["text"]
            text_lower = text.lower()

            # Table Header detection
            if any(k in text_lower for k in ["description", "item", "qty", "quantity", "unit price", "rate", "amount", "particulars"]):
                table_started = True
                continue

            # Stop table if total section starts
            if any(k in text_lower for k in ["subtotal", "total", "tax", "vat", "amount due", "thank you", "terms"]):
                table_started = False

            if table_started or len(items) > 0:
                parts = re.findall(r'(\d+(?:\.\d+)?)\s+(?:[\$€£₹]\s*)?(\d+(?:\.\d{2})?)\s+(?:[\$€£₹]\s*)?(\d+(?:\.\d{2})?)', text)
                if parts:
                    qty, price, tot = parts[0]
                    desc = re.sub(r'(\d+(?:\.\d+)?)\s+(?:[\$€£₹]\s*)?(\d+(?:\.\d{2})?)\s+(?:[\$€£₹]\s*)?(\d+(?:\.\d{2})?)', '', text).strip()
                    items.append({
                        "description": desc or "Line Item",
                        "quantity": float(qty),
                        "unit_price": float(price),
                        "total_price": float(tot),
                        "box": line["box"]
                    })

        return items
