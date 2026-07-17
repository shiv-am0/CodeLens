# CodeLens Deployment Guide

Deploy the entire CodeLens stack for **free** using Vercel (frontend), Render (backend), and Supabase (database).

---

## Prerequisites

- [GitHub account](https://github.com)
- [OpenAI API key](https://platform.openai.com/api-keys)
- [Supabase account](https://supabase.com) (free)
- [Render account](https://render.com) (free, no credit card required)
- [Vercel account](https://vercel.com) (free, GitHub login)

---

## Step 1: Configure Environment Variables

Generate an encryption key for storing API keys in the database:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save this key — you'll need it for both Render and your local `.env` file.

---

## Step 2: Database — Supabase

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click **New project**
   - Name: `codelens`
   - Database password: **save this securely**
   - Region: choose the closest to you
   - Pricing Plan: **Free**
3. Wait for the database to provision (~2 minutes)
4. Go to **Project Settings → Database → Connection string**
5. Copy the connection string (it will look like `postgresql://postgres:xxxx@xxxx.pooler.supabase.com:6543/postgres`)

### Enable pgvector

1. Go to **SQL Editor** in the Supabase dashboard
2. Run this SQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Fix Connection Strings

Supabase gives you two connection strings:
- **Session pooler** (port 6543) — use this for the app
- **Direct connection** (port 5432) — use this for migrations/one-off tasks

For the app, add `?pgbouncer=true&connection_limit=1` to the async connection string:

Example:
```
DATABASE_URL=postgresql+asyncpg://postgres.xxxx:password@aws-0-xx.pooler.supabase.com:6543/postgres?pgbouncer=true&connection_limit=1
DATABASE_URL_SYNC=postgresql://postgres.xxxx:password@aws-0-xx.pooler.supabase.com:6543/postgres?pgbouncer=true&connection_limit=1
```

---

## Step 3: Backend — Render

1. Go to [render.com](https://render.com) and sign in
2. Click **New + → Blueprint**
3. Connect your GitHub repository
4. Select the `codelens` repo
5. Render will detect the `render.yaml` file and show:
   - A **Web Service** (codelens-backend)
   - A **PostgreSQL database** (codelens-db)
6. Click **Apply**
7. Render will deploy — this takes ~5 minutes

### After Deploy

1. Go to your Render dashboard → **Environment**
2. Set these **secret** environment variables:

| Variable | Value |
|---|---|
| `ADMIN_PASSWORD` | Choose a strong admin password |
| `ENCRYPTION_KEY` | The key generated in Step 1 |
| `GITHUB_TOKEN` | (Optional) Your GitHub token |

> **Note:** `DATABASE_URL` is automatically linked from the Render PostgreSQL. If you prefer using Supabase instead (recommended), override it in Environment → DATABASE_URL with the Supabase connection string and delete the Render database.

### Verify the Backend

Once deployed, visit `https://your-app.onrender.com/api/health`. You should see:

```json
{"status": "ok", "app": "CodeLens"}
```

---

## Step 4: Frontend — Vercel

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click **Add New → Project**
3. Import your `codelens` repository
4. Vercel auto-detects Next.js — keep the default settings
5. Under **Environment Variables**, add:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://your-app.onrender.com/api` |

Replace the URL with your actual Render backend URL.

6. Click **Deploy**
7. Wait ~2 minutes for the build

### Verify the Frontend

Visit `https://your-app.vercel.app` — you should see the CodeLens landing page.

---

## Step 5: Add Your OpenAI Key via Admin Panel

1. Open your backend URL: `https://your-app.onrender.com/admin/login`
2. Log in with the `ADMIN_PASSWORD` you set
3. Click **Add New Key**
   - **Name:** `My OpenAI Key` (or any label)
   - **Key:** Your actual OpenAI API key (`sk-...`)
4. Click **Add Key**
5. The key is now encrypted in the database and ready to use

> The admin panel also supports multiple keys for rotation. Add as many as you like.

---

## Step 6: Keep-Alive (Prevent Spin-Down)

### Render — Backend Keep-Alive

Render's free tier spins down after **15 minutes** of inactivity. Use [cron-job.org](https://cron-job.org) (free, no account):

1. Go to [cron-job.org](https://cron-job.org)
2. Click **Create Cronjob**
3. URL: `https://your-app.onrender.com/api/health`
4. Interval: **Every 14 minutes**
5. Save

### Supabase — Database Keep-Alive

Supabase pauses after **7 days** of no database requests. Create a GitHub Actions cron:

In your repo, create `.github/workflows/keepalive.yml`:

```yaml
name: Keep Supabase Alive
on:
  schedule:
    - cron: "0 0 */3 * *"
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -s "https://your-app.onrender.com/api/health"
```

---

## Updating API Keys

No redeployment needed:

1. Go to `https://your-app.onrender.com/admin/login`
2. Log in
3. **Add** new keys, **disable** old ones, or **delete** them
4. The backend picks up changes within 5 minutes (or instantly if you add a new key)

---

## Troubleshooting

### Backend fails to start
- Check `DATABASE_URL` is correct and includes `?pgbouncer=true&connection_limit=1`
- Verify `ENCRYPTION_KEY` is set correctly (copy it exactly)
- Check Render logs for Python dependency errors

### Frontend shows blank page
- Verify `NEXT_PUBLIC_API_URL` is set in Vercel environment variables
- Check browser console for CORS errors
- Ensure the Render backend URL is correct (no trailing slash)

### Admin login fails
- Reset `ADMIN_PASSWORD` in Render environment settings
- The service will restart automatically

### API errors ("not configured")
- Go to the admin panel and add an OpenAI API key
- Verify the key is **active** (toggle if needed)
- Wait up to 5 minutes for the cache to refresh

### Vector search not working
- Run `CREATE EXTENSION IF NOT EXISTS vector;` in Supabase SQL Editor
- Verify the embeddings dimension matches (1536 for `text-embedding-3-small`)

---

## Architecture Diagram

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Vercel     │────▶│   Render     │────▶│  Supabase    │
│  (Next.js)  │     │  (FastAPI)   │     │ (PostgreSQL) │
│             │     │              │     │   + pgvector │
└─────────────┘     └──────────────┘     └──────────────┘
                           │
                    ┌──────┴──────┐
                    │  Admin UI   │
                    │  /admin     │
                    │  (password) │
                    └─────────────┘
```

---

## Cost Summary

| Service | Plan | Cost |
|---|---|---|
| Vercel | Hobby | $0 |
| Render | Free | $0 |
| Supabase | Free | $0 |
| cron-job.org | Free | $0 |
| OpenAI | Pay-as-you-go | ~$0.50–2/month for light usage |
| **Total** | | **$0** (plus OpenAI usage) |
