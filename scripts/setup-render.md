# Render Deployment

## Option A: One-click via render.yaml (recommended)

1. Push this repo to GitHub (see `GITHUB_PUSH.md`)
2. Go to https://render.com → Sign up with GitHub
3. Click **New +** → **Blueprint**
4. Select your `crawlforge` repo
5. Render reads `render.yaml` and creates the service
6. Set the secrets in **Environment** tab:
   - `DEEPSEEK_API_KEY` — from platform.deepseek.com
   - `DATABASE_URL` — from Neon, asyncpg format
7. Click **Manual Deploy** (per your preference — no auto-deploy)

## Option B: Manual setup

1. Render dashboard → **New +** → **Web Service**
2. Connect your GitHub repo
3. Settings:
   - **Runtime**: Docker
   - **Plan**: Free
   - **Region**: Oregon (same as Neon)
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Command**: (leave empty, uses CMD)
   - **Health Check Path**: `/health`
4. Add env vars (same as Option A)
5. **Create Web Service** → wait ~5-10 min for first build (Chromium download is heavy)

## Post-deploy

1. Once deployed, Render gives you a URL like `https://crawlforge-xxx.onrender.com`
2. Visit it — dashboard should load
3. Test crawl: `curl -X POST https://crawlforge-xxx.onrender.com/api/v1/crawl -H "Content-Type: application/json" -d '{"url": "https://example.com", "summarize": true}'`
4. Note: free tier sleeps after 15min idle → 50s cold start on first hit