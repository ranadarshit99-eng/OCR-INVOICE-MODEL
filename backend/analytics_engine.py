import csv
import io
import json

class AnalyticsEngine:
    def __init__(self):
        self.history = []

    def log_analysis(self, invoice_data):
        self.history.append(invoice_data)

    def get_summary_stats(self):
        total_count = len(self.history)
        if total_count == 0:
            return {
                "total_invoices_processed": 0,
                "total_amount_sum": 0.0,
                "avg_confidence": 0.0,
                "math_pass_rate": 100.0,
                "vendor_breakdown": {}
            }

        total_sum = sum([((item.get("total_amount") or {}).get("value", 0.0) if isinstance(item, dict) else 0.0) for item in self.history])
        avg_conf = sum([(item.get("overall_confidence", 0.0) if isinstance(item, dict) else 0.0) for item in self.history]) / total_count
        valid_math_count = sum([1 for item in self.history if isinstance(item, dict) and (item.get("math_verification") or {}).get("is_valid", False)])

        vendors = {}
        for item in self.history:
            if not isinstance(item, dict):
                continue
            v_name = (item.get("vendor") or {}).get("value", "Unknown Vendor")
            amt = (item.get("total_amount") or {}).get("value", 0.0)
            vendors[v_name] = round(vendors.get(v_name, 0.0) + amt, 2)

        return {
            "total_invoices_processed": total_count,
            "total_amount_sum": round(total_sum, 2),
            "avg_confidence": round(avg_conf, 1),
            "math_pass_rate": round((valid_math_count / total_count) * 100.0, 1),
            "vendor_breakdown": vendors
        }

    def export_csv(self, invoices_data_list):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Invoice Number", "Invoice Date", "Due Date", "Vendor Name", "Customer Name",
            "Subtotal", "Tax", "Discount", "Total Amount", "Currency", "Math Verified", "Confidence %"
        ])

        for inv in invoices_data_list:
            if not isinstance(inv, dict):
                continue
            writer.writerow([
                (inv.get("invoice_number") or {}).get("value", ""),
                (inv.get("invoice_date") or {}).get("value", ""),
                (inv.get("due_date") or {}).get("value", ""),
                (inv.get("vendor") or {}).get("value", ""),
                (inv.get("customer") or {}).get("value", ""),
                (inv.get("subtotal") or {}).get("value", 0.0),
                (inv.get("tax") or {}).get("value", 0.0),
                (inv.get("discount") or {}).get("value", 0.0),
                (inv.get("total_amount") or {}).get("value", 0.0),
                inv.get("currency", "USD"),
                (inv.get("math_verification") or {}).get("is_valid", False),
                inv.get("overall_confidence", 0.0)
            ])

        return output.getvalue()
