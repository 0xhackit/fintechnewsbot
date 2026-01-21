# Render + Vercel Deployment Guide

## ✅ Backend Deployment (Render)

### 1. Deploy to Render

1. Go to [render.com](https://render.com)
2. Sign up/login with GitHub
3. Click **"New +"** → **"Web Service"**
4. Connect repository: `0xhackit/fintechnewsbot`
5. Configure:
   - **Name**: `fintech-news-api`
   - **Region**: Oregon (USA) or closest to you
   - **Branch**: `main`
   - **Root Directory**: *Leave blank*
   - **Runtime**: **Docker** (auto-detected)
   - **Instance Type**: **Free**
6. Click **"Create Web Service"**

### 2. Wait for Build

Render will:
- Detect your `Dockerfile`
- Build the Docker image (~2-3 min)
- Deploy the container
- Give you a URL: `https://fintech-news-api.onrender.com`

### 3. Test Backend

```bash
# Health check
curl https://fintech-news-api.onrender.com/

# Get news
curl https://fintech-news-api.onrender.com/api/news

# Get categories
curl https://fintech-news-api.onrender.com/api/categories
```

**Expected Response:**
```json
{
  "status": "ok",
  "message": "Fintech News Terminal API",
  "version": "1.0.0"
}
```

---

## ✅ Frontend Deployment (Vercel)

### 4. Update Frontend Environment Variable

If your Render URL is different from `fintech-news-api.onrender.com`, update:

```bash
cd frontend
echo "VITE_API_URL=https://YOUR-RENDER-URL.onrender.com/api" > .env.production
```

### 5. Deploy to Vercel

```bash
# Install Vercel CLI (if not installed)
npm i -g vercel

# Login
vercel login

# Deploy from frontend directory
cd frontend
vercel --prod
```

**Deployment prompts:**
- Set up and deploy? **Y**
- Which scope? Choose your account
- Link to existing project? **N**
- Project name? `fintech-news-terminal`
- In which directory is your code located? **./frontend**
- Want to override settings? **N**

### 6. Get Frontend URL

Vercel will output:
```
✅  Production: https://fintech-news-terminal.vercel.app
```

---

## ✅ Verification

### Test Complete Stack

1. **Open frontend**: `https://fintech-news-terminal.vercel.app`
2. **Check for news items** - should see live data
3. **Filter by category** - click Stablecoins, RWA, etc.
4. **Check auto-refresh** - wait 5 minutes, new items appear

### Troubleshooting

**Backend shows "No data":**
- Check if GitHub Actions ran: https://github.com/0xhackit/fintechnewsbot/actions
- Verify `out/items_last24h.json` exists in repo
- Render automatically pulls latest from GitHub on each deploy

**Frontend shows "Connection Error":**
- Open browser console (F12)
- Check for CORS errors
- Verify `VITE_API_URL` in `.env.production` is correct
- Test backend directly: `curl https://your-render-url.onrender.com/api/news`

**Render service is sleeping:**
- Free tier sleeps after 15 min of inactivity
- First request takes ~30 seconds to wake up
- Subsequent requests are fast

---

## 🔄 Auto-Deploy Setup

Both platforms auto-deploy on `git push`:

### Render Auto-Deploy
- Already configured!
- Every push to `main` triggers rebuild
- Check: Render Dashboard → Settings → "Auto-Deploy" should be ON

### Vercel Auto-Deploy
- Link GitHub repo to Vercel project
- Vercel Dashboard → Settings → Git
- Connect repository: `0xhackit/fintechnewsbot`
- Root Directory: `frontend`
- Every push to `main` → auto-deploy

---

## 📊 Monitoring

### Render Logs
- Dashboard → Your Service → Logs tab
- Real-time streaming
- Filter by time/severity

### Vercel Analytics
- Dashboard → Your Project → Analytics tab
- View page loads, performance
- Free tier includes basic analytics

---

## 💰 Cost

### Current Setup (Free Forever)
- **Render Backend**: Free tier (500 hours/month, sleeps after 15 min)
- **Vercel Frontend**: Free tier (100GB bandwidth, unlimited builds)
- **GitHub Actions**: Free for public repos
- **Total**: $0/month ✅

### Upgrade Options

**Render (If you need always-on):**
- Starter Plan: $7/month
- No sleep, 512MB RAM
- Custom domains with SSL

**Vercel (If you need more bandwidth):**
- Pro Plan: $20/month
- 1TB bandwidth
- Advanced analytics

---

## 🎯 Next Steps

After deployment works:

1. **Custom Domain** (optional)
   - Buy domain (Namecheap, Google Domains)
   - Render: Add custom domain in settings
   - Vercel: Add custom domain in settings
   - Update DNS records

2. **Monitoring** (optional)
   - Add Sentry for error tracking
   - Add UptimeRobot for uptime monitoring
   - Set up email alerts

3. **Performance** (if needed)
   - Enable Render's Redis caching
   - Add CDN for static assets
   - Optimize frontend bundle size

---

## 📝 URLs Summary

After deployment, save these:

```
Backend API: https://fintech-news-api.onrender.com
Frontend:    https://fintech-news-terminal.vercel.app

API Health:  https://fintech-news-api.onrender.com/api/health
API News:    https://fintech-news-api.onrender.com/api/news
API Stats:   https://fintech-news-api.onrender.com/api/stats
```

---

**Questions?** Check:
1. Render logs for backend errors
2. Browser console for frontend errors
3. GitHub Actions for pipeline errors
4. Network tab for API calls
