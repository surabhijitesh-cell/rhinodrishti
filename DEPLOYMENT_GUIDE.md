# Rhino Drishti - Deployment Guide
## Architecture: Vercel (Frontend) + Render (Backend) + MongoDB Atlas (Database)

---

## Step 1: Set Up MongoDB Atlas (Free Tier)

1. Go to [https://www.mongodb.com/atlas](https://www.mongodb.com/atlas) and create a free account
2. Create a **Free Shared Cluster** (M0 - 512MB, sufficient for ~2 years of data)
3. Choose **Mumbai (ap-south-1)** region for lowest latency
4. Under **Database Access**, create a database user:
   - Username: `rhino_admin` (or your choice)
   - Password: generate a strong password and **save it**
5. Under **Network Access**, add `0.0.0.0/0` to allow connections from Render
6. Click **Connect** → **Drivers** → Copy the connection string:
   ```
   mongodb+srv://rhino_admin:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
   Replace `<password>` with your actual password.

---

## Step 2: Deploy Backend on Render

### Option A: Via Render Dashboard (Recommended)

1. Push your code to a GitHub repository (use "Save to Github" in Emergent)
2. Go to [https://render.com](https://render.com) and sign in
3. Click **New** → **Web Service**
4. Connect your GitHub repo and select the repository
5. Configure:
   - **Name**: `rhino-drishti-api`
   - **Region**: Singapore (closest to India)
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free

6. Add **Environment Variables** (under Environment tab):

   | Key | Value |
   |-----|-------|
   | `MONGO_URL` | `mongodb+srv://rhino_admin:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority` |
   | `DB_NAME` | `rhino_drishti` |
   | `EMERGENT_LLM_KEY` | Your Emergent LLM Key (`sk-emergent-...`) |
   | `CORS_ORIGINS` | `https://your-app.vercel.app` (update after Step 3) |

7. Click **Create Web Service**
8. Wait for build to complete. Note your Render URL: `https://rhino-drishti-api.onrender.com`

### Option B: Via render.yaml (Blueprint)

The file `backend/render.yaml` is already created. You can use Render Blueprints to auto-deploy from it.

---

## Step 3: Deploy Frontend on Vercel

1. Go to [https://vercel.com](https://vercel.com) and sign in with GitHub
2. Click **Add New** → **Project**
3. Import your GitHub repository
4. Configure:
   - **Framework Preset**: Create React App
   - **Root Directory**: `frontend`
   - **Build Command**: `yarn build`
   - **Output Directory**: `build`

5. Add **Environment Variable**:

   | Key | Value |
   |-----|-------|
   | `REACT_APP_BACKEND_URL` | `https://rhino-drishti-api.onrender.com` (your Render URL from Step 2) |

6. Click **Deploy**
7. Note your Vercel URL: `https://your-app.vercel.app`

---

## Step 4: Update CORS on Render

After getting your Vercel frontend URL:

1. Go to Render Dashboard → Your Web Service → **Environment**
2. Update the `CORS_ORIGINS` variable:
   ```
   https://your-app.vercel.app
   ```
   If you have a custom domain too, comma-separate them:
   ```
   https://your-app.vercel.app,https://yourdomain.com
   ```
3. The service will auto-redeploy with the updated CORS.

---

## Step 5: Migrate Existing Data (Optional)

To export data from the current Emergent preview environment to MongoDB Atlas:

```bash
# Export from current MongoDB
mongodump --db test_database --out /tmp/rhino_backup

# Import to Atlas (run from your local machine after downloading the dump)
mongorestore --uri "mongodb+srv://rhino_admin:<password>@cluster0.xxxxx.mongodb.net" --db rhino_drishti /tmp/rhino_backup/test_database
```

---

## Important Notes

### Render Free Tier Limitations
- **Spin-down**: Free services spin down after 15 minutes of inactivity. First request after spin-down takes ~30-60 seconds (cold start)
- **750 hours/month**: Sufficient for 1 service running 24/7
- **APScheduler**: The background scheduler (RSS fetch every 30 min) will only run while the service is active. On the free tier, it pauses during spin-down. Consider upgrading to the **Starter plan ($7/month)** for always-on service if continuous monitoring is critical.

### Vercel Free Tier
- Generous for frontend hosting — no spin-down issues
- 100GB bandwidth/month (more than enough)

### MongoDB Atlas Free Tier (M0)
- 512MB storage (handles ~2+ years of your data at current ingestion rate)
- Shared RAM — adequate for your query patterns
- Auto-scaling available if you upgrade later

---

## Custom Domain Setup

### Vercel (Frontend)
1. Go to Project Settings → Domains
2. Add your domain → Follow DNS configuration instructions

### Render (Backend)
1. Go to Service Settings → Custom Domains
2. Add your API subdomain (e.g., `api.yourdomain.com`)
3. Update frontend's `REACT_APP_BACKEND_URL` to match

---

## Environment Variables Summary

### Render (Backend)
| Variable | Description |
|----------|-------------|
| `MONGO_URL` | MongoDB Atlas connection string |
| `DB_NAME` | `rhino_drishti` |
| `EMERGENT_LLM_KEY` | Emergent Universal LLM Key |
| `CORS_ORIGINS` | Vercel frontend URL |

### Vercel (Frontend)
| Variable | Description |
|----------|-------------|
| `REACT_APP_BACKEND_URL` | Render backend URL (no trailing slash) |
