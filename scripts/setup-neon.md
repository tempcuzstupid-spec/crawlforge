# Neon Postgres Setup

1. Go to https://console.neon.tech and sign up (free, GitHub login works)
2. Click **Create Project**
   - Name: `crawlforge`
   - Region: pick one close to your Render region (Oregon recommended)
   - Postgres version: 16 (default)
3. Wait ~30s for provisioning
4. Go to **Dashboard → Connection Details**
5. Copy the **Pooled connection** string (looks like):
   ```
   postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/crawlforge?sslmode=require
   ```
6. Convert it to asyncpg format for `.env`:
   ```
   postgresql+asyncpg://user:pass@ep-xxx-pooler.region.aws.neon.tech/crawlforge?ssl=require
   ```
   (note: change `sslmode=require` to `ssl=require`)
7. Paste into `.env` as `DATABASE_URL`
8. On Render, set the same as `DATABASE_URL` environment variable

Tables are auto-created on first run via `init_db()`.