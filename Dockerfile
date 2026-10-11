FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system dependencies for OpenCV and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first to keep image lightweight and fast
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and assets
COPY backend ./backend
COPY frontend ./frontend
COPY samples ./samples
COPY run_server.py .

# Pre-download and cache EasyOCR model weights during container build
RUN python -c "import easyocr; reader = easyocr.Reader(['en'], gpu=False)"

# Cloud platform port exposure
EXPOSE 8000

# Start server
CMD ["python", "run_server.py"]
