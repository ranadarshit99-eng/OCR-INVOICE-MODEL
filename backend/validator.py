import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger("InvoiceValidator")

# Global database of processed invoice numbers for duplicate detection
PROCESSED_INVOICE_STORE = set()

class InvoiceValidator:
    def __init__(self):
        pass

    def validate_gstin_format(self, gstin: str) -> bool:
        """Check if Indian GSTIN matches 15-character statutory format."""
        if not gstin:
            return False
        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
        return bool(re.match(pattern, gstin))

    def validate_financial_math(self, fin: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Subtotal - Discount + Taxes + Shipping = Grand Total."""
        subtotal = fin.get("subtotal", 0.0)
        discount = fin.get("total_discount", 0.0)
        cgst = fin.get("cgst_amount", 0.0)
        sgst = fin.get("sgst_amount", 0.0)
        igst = fin.get("igst_amount", 0.0)
        other_tax = fin.get("other_taxes", 0.0)
        shipping = fin.get("shipping_charges", 0.0)
        grand_total = fin.get("grand_total", 0.0)

        calculated_total = round(subtotal - discount + cgst + sgst + igst + other_tax + shipping, 2)
        diff = abs(calculated_total - grand_total)

        is_itr = fin.get("is_itr", False)
        if is_itr:
            is_valid = (grand_total > 0 and grand_total >= other_tax)
            diff = 0.0 if is_valid else diff
            status_msg = f"ITR Total Income ({grand_total}) and Taxes Deposited ({other_tax}) validated." if is_valid else f"Total Income ({grand_total}) is less than taxes paid ({other_tax})."
        else:
            is_valid = diff <= 1.0  # Allow 1 currency unit tolerance for rounding
            status_msg = "Total amount matches mathematical sum" if is_valid else f"Discrepancy of {diff:.2f} detected between calculated sum ({calculated_total}) and recorded total ({grand_total})."

        return {
            "is_valid": is_valid,
            "calculated_grand_total": calculated_total,
            "recorded_grand_total": grand_total,
            "discrepancy": round(diff, 2),
            "status_message": status_msg
        }

    def validate_tax_calculations(self, fin: Dict[str, Any]) -> Dict[str, Any]:
        """Validate if CGST equals SGST (intra-state) or IGST is present (inter-state)."""
        cgst = fin.get("cgst_amount", 0.0)
        sgst = fin.get("sgst_amount", 0.0)
        igst = fin.get("igst_amount", 0.0)
        subtotal = fin.get("subtotal", 0.0)

        cgst_sgst_match = (cgst == sgst) if (cgst > 0 or sgst > 0) else True
        tax_present = (cgst + sgst + igst + fin.get("other_taxes", 0.0)) > 0

        estimated_tax_rate = 0.0
        if subtotal > 0 and tax_present:
            estimated_tax_rate = round(((cgst + sgst + igst) / subtotal) * 100, 1)

        return {
            "is_valid": cgst_sgst_match,
            "cgst_sgst_equal": cgst_sgst_match,
            "tax_present": tax_present,
            "estimated_tax_rate_percent": estimated_tax_rate,
            "status_message": "Tax calculations consistent" if cgst_sgst_match else "CGST and SGST mismatch in intra-state tax split."
        }

    def detect_missing_fields(self, extracted_data: Dict[str, Any]) -> List[str]:
        """Identify critical mandatory missing fields."""
        missing = []

        basic = extracted_data.get("basic_details", {})
        if not basic.get("invoice_number"):
            missing.append("Invoice Number")
        if not basic.get("invoice_date"):
            missing.append("Invoice Date")

        seller = extracted_data.get("seller_details", {})
        if not seller.get("seller_name"):
            missing.append("Seller Name")
        if not seller.get("seller_gstin"):
            missing.append("Seller GSTIN / Tax ID")

        buyer = extracted_data.get("buyer_details", {})
        if not buyer.get("buyer_name"):
            missing.append("Buyer Name")

        fin = extracted_data.get("financial_details", {})
        if not fin.get("grand_total") or fin.get("grand_total") == 0.0:
            missing.append("Grand Total")

        return missing

    def check_duplicate(self, invoice_number: str) -> Dict[str, Any]:
        """Check if invoice number has been processed previously."""
        if not invoice_number:
            return {"is_duplicate": False, "message": "No invoice number to check."}

        clean_num = invoice_number.strip().upper()
        if clean_num in PROCESSED_INVOICE_STORE:
            return {
                "is_duplicate": True,
                "message": f"WARNING: Invoice number '{clean_num}' was previously processed in the system!"
            }
        else:
            PROCESSED_INVOICE_STORE.add(clean_num)
            return {
                "is_duplicate": False,
                "message": f"Invoice number '{clean_num}' is unique."
            }

    def evaluate_authenticity(
        self,
        extracted_data: Dict[str, Any],
        ocr_confidence: float,
        stamp_sig_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall authenticity score and verification breakdown (Category G fields 40-47)."""
        score = 100.0
        checks = []

        # Check 1: OCR Confidence
        if ocr_confidence >= 80.0:
            checks.append({"name": "OCR Text Clarity", "status": "PASS", "points": "+20"})
        else:
            score -= 15.0
            checks.append({"name": "OCR Text Clarity", "status": "WARNING", "points": "-15"})

        # Check 2: Mandatory Seller Information
        seller = extracted_data.get("seller_details", {})
        if seller.get("seller_name") and seller.get("seller_address"):
            checks.append({"name": "Seller Profile & Address", "status": "PASS", "points": "+20"})
        else:
            score -= 15.0
            checks.append({"name": "Seller Profile & Address", "status": "FAIL", "points": "-15"})

        # Check 3: Tax ID (GSTIN) Format
        seller_gstin = seller.get("seller_gstin", "")
        if self.validate_gstin_format(seller_gstin):
            checks.append({"name": "GSTIN Statutory Format", "status": "PASS", "points": "+20"})
        else:
            score -= 10.0
            checks.append({"name": "GSTIN Statutory Format", "status": "WARNING", "points": "-10"})

        # Check 4: Financial Math Verification
        math_res = self.validate_financial_math(extracted_data.get("financial_details", {}))
        if math_res["is_valid"]:
            checks.append({"name": "Total Amount Math Audit", "status": "PASS", "points": "+20"})
        else:
            score -= 20.0
            checks.append({"name": "Total Amount Math Audit", "status": "FAIL", "points": "-20"})

        # Check 5: Stamp or Signature Presence
        has_stamp_sig = stamp_sig_data.get("stamp_detected", False) or stamp_sig_data.get("signature_detected", False)
        if has_stamp_sig:
            checks.append({"name": "Stamp / Signature Seal", "status": "PASS", "points": "+20"})
        else:
            score -= 10.0
            checks.append({"name": "Stamp / Signature Seal", "status": "WARNING", "points": "-10"})

        score = max(0.0, round(score, 1))

        return {
            "authenticity_score": score,
            "grade": "Authentic / High Trust" if score >= 80 else ("Review Required" if score >= 50 else "High Risk / Audit Needed"),
            "verification_checks": checks
        }

    def process_verification(
        self,
        extracted_data: Dict[str, Any],
        ocr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build Category G: Verification & Automation output."""
        inv_num = extracted_data["basic_details"].get("invoice_number", "")
        dup_info = self.check_duplicate(inv_num)
        missing_fields = self.detect_missing_fields(extracted_data)
        amount_val = self.validate_financial_math(extracted_data.get("financial_details", {}))
        tax_val = self.validate_tax_calculations(extracted_data.get("financial_details", {}))
        
        ocr_conf = ocr_result.get("average_confidence", 85.0)
        boxes = ocr_result.get("words_with_boxes", [])
        stamp_sig = ocr_result.get("stamp_signature", {})

        auth_info = self.evaluate_authenticity(extracted_data, ocr_conf, stamp_sig)

        return {
            "duplicate_invoice_detection": dup_info,
            "missing_field_detection": {
                "count": len(missing_fields),
                "missing_fields": missing_fields,
                "has_missing": len(missing_fields) > 0
            },
            "total_amount_validation": amount_val,
            "tax_calculation_validation": tax_val,
            "ocr_confidence_score": ocr_conf,
            "source_location_count": len(boxes),
            "source_locations": boxes[:100],  # Bounding box coordinates list
            "invoice_authenticity": auth_info,
            "signature_stamp_presence": stamp_sig
        }
