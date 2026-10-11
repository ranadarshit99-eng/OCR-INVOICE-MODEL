import os
from PIL import Image, ImageDraw, ImageFont
import io

def generate_sample_invoice_image() -> bytes:
    """Generate a high-clarity synthetic sample invoice PNG image with stamp and line items."""
    width, height = 1000, 1300
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Use standard crisp fonts
    try:
        font_title = ImageFont.truetype("arial.ttf", 30)
        font_subtitle = ImageFont.truetype("arialbd.ttf", 20)
        font_header = ImageFont.truetype("arialbd.ttf", 16)
        font_body = ImageFont.truetype("arial.ttf", 15)
        font_bold = ImageFont.truetype("arialbd.ttf", 15)
    except IOError:
        font_title = font_subtitle = font_header = font_body = font_bold = ImageFont.load_default()

    # Draw Header Banner
    draw.rectangle([(0, 0), (width, 100)], fill="#0f172a")
    draw.text((40, 32), "NEXUS TECH SOLUTIONS PVT LTD", fill="#ffffff", font=font_title)
    draw.text((700, 35), "TAX INVOICE", fill="#38bdf8", font=font_subtitle)

    # Seller Info Section
    draw.text((40, 120), "Seller / Vendor Details:", fill="#475569", font=font_header)
    draw.text((40, 148), "Nexus Tech Solutions Pvt Ltd", fill="#0f172a", font=font_bold)
    draw.text((40, 172), "102 Cyber City, Sector 24, Gurugram, HR 122002", fill="#334155", font=font_body)
    draw.text((40, 196), "GSTIN: 07AAAAA9999A1Z5 | Phone: +91 98100 12345", fill="#334155", font=font_body)
    draw.text((40, 220), "Email: billing@nexustech.com", fill="#334155", font=font_body)

    # Invoice Details Block
    draw.rectangle([(640, 120), (960, 245)], outline="#cbd5e1", width=2)
    draw.text((655, 132), "Invoice No: INV-2026-8842", fill="#0f172a", font=font_bold)
    draw.text((655, 160), "Invoice Date: 10/10/2026", fill="#334155", font=font_body)
    draw.text((655, 188), "Due Date: 25/10/2026", fill="#334155", font=font_body)
    draw.text((655, 216), "PO Number: PO-77391", fill="#334155", font=font_body)

    # Buyer Info Section
    draw.line([(40, 265), (960, 265)], fill="#e2e8f0", width=1)
    draw.text((40, 280), "Billed To (Customer):", fill="#475569", font=font_header)
    draw.text((40, 308), "Apex Global Logistics Ltd", fill="#0f172a", font=font_bold)
    draw.text((40, 332), "Plot 45, Bandra Kurla Complex, Mumbai, MH 400051", fill="#334155", font=font_body)
    draw.text((40, 356), "GSTIN: 27BBBBB5555B1Z9", fill="#334155", font=font_body)

    # Table Header
    draw.rectangle([(40, 400), (960, 440)], fill="#f1f5f9")
    draw.text((55, 412), "Item Description", fill="#0f172a", font=font_header)
    draw.text((470, 412), "HSN/SAC", fill="#0f172a", font=font_header)
    draw.text((600, 412), "Qty", fill="#0f172a", font=font_header)
    draw.text((690, 412), "Unit Price", fill="#0f172a", font=font_header)
    draw.text((830, 412), "Total (INR)", fill="#0f172a", font=font_header)

    # Line Items
    items = [
        ("Cloud Server Enterprise Hosting - Annual", "8471", "2", "INR 45,000.00", "INR 90,000.00"),
        ("AI OCR API Integration Services", "9983", "1", "INR 35,000.00", "INR 35,000.00"),
        ("Managed Cybersecurity SLA Suite", "9983", "1", "INR 25,000.00", "INR 25,000.00"),
    ]

    y = 455
    for item in items:
        draw.text((55, y), item[0], fill="#334155", font=font_body)
        draw.text((470, y), item[1], fill="#334155", font=font_body)
        draw.text((600, y), item[2], fill="#334155", font=font_body)
        draw.text((690, y), item[3], fill="#334155", font=font_body)
        draw.text((830, y), item[4], fill="#334155", font=font_body)
        draw.line([(40, y + 32), (960, y + 32)], fill="#f1f5f9", width=1)
        y += 45

    # Financial Summary Box
    y += 15
    draw.text((600, y), "Subtotal:", fill="#334155", font=font_body)
    draw.text((830, y), "INR 150,000.00", fill="#334155", font=font_body)
    y += 32
    draw.text((600, y), "CGST @ 9%:", fill="#334155", font=font_body)
    draw.text((830, y), "INR 13,500.00", fill="#334155", font=font_body)
    y += 32
    draw.text((600, y), "SGST @ 9%:", fill="#334155", font=font_body)
    draw.text((830, y), "INR 13,500.00", fill="#334155", font=font_body)
    y += 35
    draw.line([(600, y), (960, y)], fill="#0f172a", width=2)
    y += 12
    draw.text((600, y), "Grand Total:", fill="#0f172a", font=font_subtitle)
    draw.text((830, y), "INR 177,000.00", fill="#0f172a", font=font_subtitle)

    # Payment Details & Bank Info
    draw.rectangle([(40, 840), (520, 1020)], outline="#cbd5e1", width=1)
    draw.text((55, 855), "Payment & Bank Details:", fill="#0f172a", font=font_header)
    draw.text((55, 888), "Bank Name: HDFC Bank Ltd", fill="#334155", font=font_body)
    draw.text((55, 915), "Account No: 50200018923410", fill="#334155", font=font_body)
    draw.text((55, 942), "IFSC Code: HDFC0000240", fill="#334155", font=font_body)
    draw.text((55, 969), "UPI ID: nexustech@hdfcbank", fill="#334155", font=font_body)
    draw.text((55, 994), "Payment Status: Unpaid", fill="#dc2626", font=font_bold)

    # Blue Rubber Stamp Simulation
    stamp_center = (780, 930)
    draw.ellipse([stamp_center[0]-65, stamp_center[1]-65, stamp_center[0]+65, stamp_center[1]+65], outline="#2563eb", width=4)
    draw.text((stamp_center[0]-50, stamp_center[1]-18), "NEXUS TECH", fill="#2563eb", font=font_header)
    draw.text((stamp_center[0]-42, stamp_center[1]+8), "VERIFIED", fill="#2563eb", font=font_header)

    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
