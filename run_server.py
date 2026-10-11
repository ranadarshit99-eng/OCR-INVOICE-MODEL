import os
import sys
import uvicorn

def main():
    print("=" * 65)
    print("     OCR-BASED INVOICE ANALYSIS SYSTEM - MULTI-ENGINE AI     ")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    print("\n[1/2] Verifying System & Invoice Dataset...")
    try:
        from dataset_manager import DatasetManager
        dm = DatasetManager()
        invoices = dm.get_all_invoices()
        print(f" -> Dataset verified: {len(invoices)} total invoice files available.")
    except Exception as e:
        print(f" -> Dataset notice: {e}")

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8005))
    print("\n[2/2] Launching FastAPI Web Application Server...")
    print(f" -> App Dashboard URL: http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}")
    print(" -> Press Ctrl+C to stop the server\n")

    uvicorn.run("main:app", app_dir=backend_dir, host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
