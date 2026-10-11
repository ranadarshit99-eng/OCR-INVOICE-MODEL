# 🚀 InvoiceAI Online Deployment Guide

Your InvoiceAI system is packaged and ready for online deployment. Choose any of the methods below based on your preference.

---

## ⚡ Option 1: Instant Live Public URL in 30 Seconds (Zero Configuration)
If you want to share the app with evaluators, teachers, or test it on your mobile phone right now without signing up for any cloud provider:

1. **Start the local server:**
   ```bash
   python run_server.py
   ```
2. **Open a second terminal window and run Cloudflare Tunnel (Free & Instant HTTPS):**
   ```bash
   npx -y cloudflared tunnel --url http://127.0.0.1:8005
   ```
   *(Or using Localtunnel:)*
   ```bash
   npx -y localtunnel --port 8005
   ```
3. A live HTTPS link (e.g., `https://random-words.trycloudflare.com`) will appear in your terminal. Anyone can access your app live on the internet!

---

## 🌐 Option 2: 100% Free 24/7 Cloud Hosting on Hugging Face Spaces (Recommended for AI / OCR)
Hugging Face Spaces provides **16 GB RAM CPU** completely free, making it ideal for deep learning models like EasyOCR and PyTorch.

1. Go to [https://huggingface.co/spaces](https://huggingface.co/spaces) and click **"Create new Space"**.
2. Fill in:
   - **Space Name:** `invoice-ai-ocr`
   - **License:** `apache-2.0` or `mit`
   - **Space SDK:** Select **Docker** (Blank)
   - **Visibility:** Public
3. Click **"Create Space"**.
4. Push your files to the Space repository:
   ```bash
   git init
   git remote add origin https://huggingface.co/spaces/<YOUR_USERNAME>/invoice-ai-ocr
   git add .
   git commit -m "Deploy InvoiceAI"
   git push -u origin main --force
   ```
5. Hugging Face will build the `Dockerfile` and launch your live application with a permanent URL like:
   `https://<YOUR_USERNAME>-invoice-ai-ocr.hf.space`

---

## ☁️ Option 3: Deploy to Render.com (Automated CI/CD from GitHub)
Render deploys web applications automatically from GitHub repositories.

1. **Initialize Git and push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit for online deployment"
   git branch -M main
   # Create a repository on github.com, then run:
   git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO>.git
   git push -u origin main
   ```
2. Go to [https://dashboard.render.com](https://dashboard.render.com) and click **"New +" ➔ "Web Service"**.
3. Select your GitHub repository.
4. Render will detect the `Dockerfile` automatically:
   - **Name:** `invoice-ai-ocr`
   - **Runtime:** `Docker`
   - **Instance Type:** Starter (or Free tier)
5. Click **"Deploy Web Service"**.
6. Your app will be live at `https://invoice-ai-ocr.onrender.com`.

---

## 🚂 Option 4: Deploy to Railway.app
1. Go to [https://railway.app](https://railway.app) and click **"New Project"**.
2. Select **"Deploy from GitHub repo"** and choose your repository.
3. Railway detects the `Dockerfile` and builds the service automatically.
4. Under **Settings ➔ Networking**, click **"Generate Domain"** to get your public HTTPS URL.

---

## 🐳 Option 5: Self-Hosted Docker Container (VPS / AWS / DigitalOcean)
To run the production container anywhere:
```bash
docker build -t invoice-ai .
docker run -d -p 8000:8000 --name invoice-ai-app invoice-ai
```
Or using docker-compose:
```bash
docker-compose up -d --build
```
Your app will be available at `http://<YOUR_SERVER_IP>:8000`.
