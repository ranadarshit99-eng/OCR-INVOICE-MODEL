import os
import glob
import logging
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("DatasetManager")

class DatasetManager:
    def __init__(self, sample_dir=None):
        self.dataset_id = "osamahosamabdellatif/high-quality-invoice-images-for-ocr"
        self.cached_path = None
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.sample_dir = sample_dir or os.path.join(base_dir, "samples")
        self.uploads_dir = os.path.join(base_dir, "uploads")
        os.makedirs(self.sample_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        self._cached_invoices = None
        self._filename_to_path = {}
        
        self._ensure_sample_invoices()
        self.download_dataset()
        self._build_invoice_cache()

    def download_dataset(self):
        """Attempts to retrieve Kaggle dataset path safely without network blocking."""
        cache_base = os.path.expanduser(r"~\.cache\kagglehub\datasets\osamahosamabdellatif\high-quality-invoice-images-for-ocr")
        if os.path.exists(cache_base):
            versions = glob.glob(os.path.join(cache_base, "versions", "*"))
            if versions:
                latest = max(versions, key=os.path.getmtime)
                self.cached_path = latest
                logger.info(f"Kaggle Dataset found in local cache: {latest}")
                return latest
            self.cached_path = cache_base
            return cache_base

        logger.info("Kaggle dataset not in local cache; initializing with crisp sample invoices.")
        return None

    def _build_invoice_cache(self):
        """Builds in-memory index of all invoices for ultra-fast listing & lookup."""
        invoices = []
        fn_to_path = {}

        # 1. Samples directory
        if os.path.exists(self.sample_dir):
            for f in sorted(os.listdir(self.sample_dir)):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf', '.webp')):
                    full_p = os.path.join(self.sample_dir, f)
                    try:
                        sz = os.path.getsize(full_p)
                    except Exception:
                        sz = 0
                    item = {
                        "filename": f,
                        "path": full_p,
                        "source": "Sample Invoice",
                        "size_bytes": sz
                    }
                    invoices.append(item)
                    fn_to_path[f] = full_p

        # 2. Uploads directory
        if os.path.exists(self.uploads_dir):
            for f in sorted(os.listdir(self.uploads_dir)):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf', '.webp')):
                    if f not in fn_to_path:
                        full_p = os.path.join(self.uploads_dir, f)
                        try:
                            sz = os.path.getsize(full_p)
                        except Exception:
                            sz = 0
                        item = {
                            "filename": f,
                            "path": full_p,
                            "source": "Uploaded Invoice",
                            "size_bytes": sz
                        }
                        invoices.append(item)
                        fn_to_path[f] = full_p

        # 3. Kaggle dataset
        if self.cached_path and os.path.exists(self.cached_path):
            extensions = ['*.png', '*.jpg', '*.jpeg', '*.tiff']
            for ext in extensions:
                for f in glob.glob(os.path.join(self.cached_path, '**', ext), recursive=True):
                    base_name = os.path.basename(f)
                    if base_name not in fn_to_path:
                        try:
                            sz = os.path.getsize(f)
                        except Exception:
                            sz = 0
                        item = {
                            "filename": base_name,
                            "path": f,
                            "source": "Kaggle Dataset",
                            "size_bytes": sz
                        }
                        invoices.append(item)
                        fn_to_path[base_name] = f

        self._cached_invoices = invoices
        self._filename_to_path = fn_to_path
        logger.info(f"Dataset index built: {len(invoices)} total invoice files available.")

    def get_all_invoices(self):
        """Returns indexed invoices list instantly."""
        if self._cached_invoices is None:
            self._build_invoice_cache()
        return self._cached_invoices

    def get_invoice_path(self, filename: str):
        """Resolves full path for a filename in O(1)."""
        if filename in self._filename_to_path:
            return self._filename_to_path[filename]
        # Re-check sample & uploads in case a new file was just added
        sample_path = os.path.join(self.sample_dir, filename)
        if os.path.exists(sample_path):
            self._filename_to_path[filename] = sample_path
            return sample_path
        upload_path = os.path.join(self.uploads_dir, filename)
        if os.path.exists(upload_path):
            self._filename_to_path[filename] = upload_path
            return upload_path
        return None

    def add_uploaded_file(self, filename: str, path: str):
        """Registers a freshly uploaded invoice file."""
        self._filename_to_path[filename] = path
        try:
            sz = os.path.getsize(path)
        except Exception:
            sz = 0
        if self._cached_invoices is not None:
            # Prepend to list
            self._cached_invoices.insert(0, {
                "filename": filename,
                "path": path,
                "source": "Uploaded Invoice",
                "size_bytes": sz
            })

    def _ensure_sample_invoices(self):
        """Generates crisp invoice image samples if sample dir is empty."""
        sample_files = [f for f in os.listdir(self.sample_dir) if f.endswith(('.png', '.jpg'))]
        if len(sample_files) >= 3:
            return

        logger.info("Creating demo invoice sample images...")
        self._create_demo_invoice(
            os.path.join(self.sample_dir, "sample_invoice_01.png"),
            inv_num="INV-2024-8842",
            date="2024-03-15",
            vendor="Quantum Tech Solutions LLC",
            customer="Acme Enterprise Holdings",
            items=[
                ("AI Model Fine-Tuning & Deployment", "1", "1,200.00", "1,200.00"),
                ("OCR Data Pipeline Optimization", "1", "450.00", "450.00"),
                ("Cloud Host Infrastructure (Monthly)", "1", "150.00", "150.00")
            ],
            subtotal="1,800.00", tax="180.00", total="1,980.00"
        )

        self._create_demo_invoice(
            os.path.join(self.sample_dir, "sample_invoice_02.png"),
            inv_num="INV-90210",
            date="2024-02-28",
            vendor="Global Logistics & Supply Co",
            customer="Vertex Industrial Systems",
            items=[
                ("Freight Shipping & Container Handling", "2", "650.00", "1,300.00"),
                ("Customs Clearance & Documentation Fee", "1", "250.00", "250.00")
            ],
            subtotal="1,550.00", tax="155.00", total="1,705.00"
        )

        self._create_demo_invoice(
            os.path.join(self.sample_dir, "sample_invoice_03.png"),
            inv_num="INV-77401",
            date="2024-01-10",
            vendor="Apex Design & Software Agency",
            customer="Starlight Media Group",
            items=[
                ("UI/UX Mobile Design System", "1", "2,500.00", "2,500.00"),
                ("Frontend React Dashboard Engineering", "1", "3,200.00", "3,200.00")
            ],
            subtotal="5,700.00", tax="570.00", total="6,270.00"
        )

    def _create_demo_invoice(self, path, inv_num, date, vendor, customer, items, subtotal, tax, total):
        """Draws a clean professional invoice PNG image using PIL."""
        w, h = 800, 1050
        img = Image.new('RGB', (w, h), color='#FFFFFF')
        draw = ImageDraw.Draw(img)

        # Header background banner
        draw.rectangle([0, 0, w, 90], fill='#1E293B')
        draw.text((40, 25), vendor.upper(), fill='#F8FAFC')
        draw.text((w - 220, 25), "TAX INVOICE", fill='#38BDF8')

        # Divider line
        draw.line([40, 110, w - 40, 110], fill='#E2E8F0', width=2)

        # Invoice Metadata
        draw.text((40, 130), f"INVOICE NUMBER: {inv_num}", fill='#0F172A')
        draw.text((40, 155), f"INVOICE DATE: {date}", fill='#475569')
        draw.text((40, 180), f"DUE DATE: 30 Days Net", fill='#475569')

        draw.text((w - 300, 130), "BILLED TO:", fill='#0F172A')
        draw.text((w - 300, 155), customer, fill='#1E293B')
        draw.text((w - 300, 180), "100 Tech Boulevard, Suite 400", fill='#64748B')
        draw.text((w - 300, 205), "San Francisco, CA 94107", fill='#64748B')

        # Line Items Table Header
        draw.rectangle([40, 250, w - 40, 285], fill='#F1F5F9')
        draw.text((50, 260), "ITEM DESCRIPTION", fill='#334155')
        draw.text((440, 260), "QTY", fill='#334155')
        draw.text((520, 260), "UNIT PRICE ($)", fill='#334155')
        draw.text((660, 260), "TOTAL ($)", fill='#334155')

        # Table Rows
        curr_y = 300
        for item in items:
            draw.text((50, curr_y), item[0], fill='#1E293B')
            draw.text((450, curr_y), item[1], fill='#475569')
            draw.text((530, curr_y), item[2], fill='#475569')
            draw.text((660, curr_y), item[3], fill='#0F172A')
            draw.line([40, curr_y + 30, w - 40, curr_y + 30], fill='#F1F5F9', width=1)
            curr_y += 40

        # Totals Section
        tot_y = curr_y + 40
        draw.rectangle([w - 350, tot_y, w - 40, tot_y + 130], fill='#F8FAFC', outline='#CBD5E1', width=1)
        draw.text((w - 330, tot_y + 15), "SUBTOTAL:", fill='#475569')
        draw.text((w - 120, tot_y + 15), f"${subtotal}", fill='#1E293B')

        draw.text((w - 330, tot_y + 45), "TAX (10%):", fill='#475569')
        draw.text((w - 120, tot_y + 45), f"${tax}", fill='#1E293B')

        draw.line([w - 330, tot_y + 75, w - 50, tot_y + 75], fill='#E2E8F0', width=1)
        draw.text((w - 330, tot_y + 85), "TOTAL AMOUNT:", fill='#0F172A')
        draw.text((w - 120, tot_y + 85), f"${total}", fill='#0284C7')

        # Footer
        draw.line([40, h - 60, w - 40, h - 60], fill='#E2E8F0', width=1)
        draw.text((40, h - 45), "Thank you for your business! Payment terms: Due in 30 days.", fill='#94A3B8')

        img.save(path)
