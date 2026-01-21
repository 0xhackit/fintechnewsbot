# Deployment Guide - Fintech News Terminal

Complete guide to deploying your Bloomberg-style news terminal to production.

## Quick Start (Local)

```bash
# Clone and setup
git clone <your-repo>
cd fintech-news-mvp

# One-command start (recommended)
./start-dev.sh

# Or manual start:
# Terminal 1 - Backend
pip install -r api/requirements.txt
python api/main.py

# Terminal 2 - Frontend
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000 🎉

## Production Deployment Options

### Option 1: Railway (Recommended - Easiest)

**Why Railway?**
- Zero-config deployment
- Free tier available
- Auto-deploys on git push
- Provides HTTPS automatically
- No credit card for hobby projects

**Backend Deployment:**

1. Create account at [railway.app](https://railway.app)

2. Create new project → "Deploy from GitHub repo"

3. Select your repo

4. Railway auto-detects `Dockerfile` and `railway.json`

5. Click "Deploy"

6. Your API will be live at: `https://your-app.railway.app`

7. Test it:
   ```bash
   curl https://your-app.railway.app/api/news
   ```

**Frontend Deployment:**

1. Update `frontend/.env`:
   ```bash
   VITE_API_URL=https://your-app.railway.app/api
   ```

2. Build frontend:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

3. Deploy `frontend/dist/` to Vercel:
   ```bash
   npm i -g vercel
   cd frontend
   vercel deploy --prod
   ```

4. Your site will be live at: `https://your-app.vercel.app`

**Total Time:** ~10 minutes ⏱️

---

### Option 2: Render

**Backend:**

1. Sign up at [render.com](https://render.com)

2. New → Web Service

3. Connect GitHub repo

4. Settings:
   - **Name:** fintech-news-api
   - **Environment:** Python 3
   - **Build Command:** `pip install -r api/requirements.txt`
   - **Start Command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free

5. Create Web Service

6. Live at: `https://fintech-news-api.onrender.com`

**Frontend:**

1. New → Static Site

2. Settings:
   - **Build Command:** `cd frontend && npm install && npm run build`
   - **Publish Directory:** `frontend/dist`

3. Environment Variables:
   - Add: `VITE_API_URL` = `https://fintech-news-api.onrender.com/api`

4. Deploy!

**Note:** Free tier sleeps after 15 min of inactivity (first request takes ~30s to wake up)

---

### Option 3: Vercel (Frontend) + Railway (Backend)

**Best for:** Production apps with high traffic

**Backend:** Follow Railway steps above

**Frontend on Vercel:**

1. Push frontend to GitHub

2. Go to [vercel.com](https://vercel.com)

3. Import project → Select repo

4. Framework: Vite

5. Root Directory: `frontend`

6. Environment Variables:
   ```
   VITE_API_URL=https://your-backend.railway.app/api
   ```

7. Deploy!

**Advantages:**
- Global CDN (fast worldwide)
- Auto-preview deployments
- Zero config
- Free tier: 100GB bandwidth

---

### Option 4: Docker Compose (Self-hosted)

**Best for:** VPS, AWS EC2, DigitalOcean, etc.

**Prerequisites:**
- Ubuntu/Debian server
- Docker & Docker Compose installed

**Step 1: Clone repo on server**

```bash
ssh user@your-server
git clone <your-repo>
cd fintech-news-mvp
```

**Step 2: Build frontend**

```bash
cd frontend
npm install
npm run build
cd ..
```

**Step 3: Create `docker-compose.yml`**

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./out:/app/out:ro
      - ./config.json:/app/config.json:ro
    restart: unless-stopped
    environment:
      - PORT=8000

  frontend:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
    restart: unless-stopped
```

**Step 4: Create `nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Frontend
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Step 5: Deploy**

```bash
docker-compose up -d
```

**Step 6: Setup HTTPS (optional but recommended)**

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

Your site: `https://your-domain.com`

---

## Environment Variables

### Backend

No environment variables required! Backend reads from:
- `out/items_last24h.json` (updated by GitHub Actions)
- `config.json`

### Frontend

Create `frontend/.env.production`:

```bash
VITE_API_URL=https://your-backend-url.com/api
```

For development, create `frontend/.env.local`:

```bash
VITE_API_URL=http://localhost:8000/api
```

---

## Domain Setup

### Connect Custom Domain to Railway

1. Railway Dashboard → Settings → Domains

2. Add custom domain: `news.yourdomain.com`

3. Add CNAME record to your DNS:
   ```
   CNAME news.yourdomain.com → your-app.railway.app
   ```

4. Wait for DNS propagation (~5 min)

5. Railway auto-provisions SSL certificate

### Connect Custom Domain to Vercel

1. Vercel Dashboard → Settings → Domains

2. Add domain: `yourdomain.com`

3. Follow DNS instructions (usually add A/CNAME records)

4. SSL auto-configured

---

## Monitoring & Logs

### Railway

- Dashboard → Your Service → Logs
- Real-time log streaming
- Download logs

### Render

- Dashboard → Your Service → Logs tab
- Filter by date/level

### Self-hosted Docker

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Update and redeploy
git pull
docker-compose up -d --build
```

---

## CI/CD Setup

### Auto-deploy on git push (Railway)

Already configured! Railway watches your repo:

1. Make changes
2. `git push origin main`
3. Railway auto-deploys 🚀

### Auto-deploy on git push (Vercel)

Already configured! Vercel watches your repo:

1. Make changes to `frontend/`
2. `git push origin main`
3. Vercel auto-deploys 🚀

### GitHub Actions (Advanced)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Railway
        run: |
          curl -X POST ${{ secrets.RAILWAY_WEBHOOK_URL }}

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Vercel
        run: |
          npm install -g vercel
          cd frontend
          vercel --token=${{ secrets.VERCEL_TOKEN }} --prod
```

---

## Performance Optimization

### Backend

**Current:** ~50ms response time for /api/news

**Optimizations:**

1. **Add caching** (Redis or in-memory):

```python
from functools import lru_cache
import time

@lru_cache(maxsize=1)
def load_news_cached():
    return load_json(ITEMS_PATH, [])

# Invalidate cache every 5 min
cache_timestamp = time.time()
if time.time() - cache_timestamp > 300:
    load_news_cached.cache_clear()
    cache_timestamp = time.time()
```

2. **Enable gzip compression**:

```python
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

3. **Add connection pooling** (for database if you add one later)

### Frontend

**Current:** ~2s initial load

**Optimizations:**

1. **Code splitting** (already enabled via Vite)

2. **Image optimization** (if you add logos later):
   ```javascript
   import logo from './logo.png?w=200&format=webp'
   ```

3. **Service Worker for offline support**:
   ```bash
   npm install vite-plugin-pwa
   ```

4. **Lazy load components**:
   ```javascript
   const StatsPanel = lazy(() => import('./components/StatsPanel'));
   ```

---

## Scaling

### Backend (if you get high traffic)

**Railway Scaling:**
- Dashboard → Settings → Resources
- Increase Memory (512MB → 2GB)
- Add horizontal replicas (Pro plan)

**Load Balancing:**
- Deploy to multiple Railway regions
- Use Cloudflare in front for DDoS protection

### Frontend (Vercel)

- Automatically scales globally
- No action needed for 100k+ users

---

## Cost Estimates

### Free Tier (Good for 1000s of users)

- **Railway Backend:** Free (500 hours/month)
- **Vercel Frontend:** Free (100GB bandwidth)
- **Total:** $0/month ✅

### Paid Tier (For serious production)

- **Railway Backend:** $5-20/month
- **Vercel Frontend:** $0-20/month
- **Domain:** $10-15/year
- **Total:** $5-40/month

---

## Troubleshooting

### Backend not responding

```bash
# Check if backend is running
curl https://your-backend.railway.app/

# Check logs on Railway
# Dashboard → Logs tab

# Check data file exists
ls -l out/items_last24h.json
```

### Frontend shows "Connection Error"

1. Check VITE_API_URL in `.env`
2. Test backend directly: `curl <VITE_API_URL>/news`
3. Check browser console for CORS errors
4. Verify backend CORS settings allow your frontend domain

### Slow API responses

1. Check data file size: `du -h out/items_last24h.json`
2. Reduce lookback_hours in `config.json` (24 → 12)
3. Add caching (see Performance section)

### "502 Bad Gateway" on Railway

- Backend is starting up (wait 30s)
- Out of memory (increase RAM in settings)
- Check logs for Python errors

---

## Security Checklist

- [ ] HTTPS enabled (automatic on Railway/Vercel)
- [ ] CORS whitelist updated with production domains
- [ ] Rate limiting enabled (add middleware if needed)
- [ ] No sensitive data in `out/items_last24h.json`
- [ ] Git secrets not committed (use `.gitignore`)
- [ ] Dependencies updated (`pip list --outdated`, `npm outdated`)

---

## Next Steps

After deployment:

1. **Add Analytics:**
   - Google Analytics
   - Plausible (privacy-friendly)
   - PostHog (open source)

2. **Add Monitoring:**
   - Sentry for error tracking
   - UptimeRobot for uptime monitoring

3. **SEO Optimization:**
   - Add meta tags
   - Generate sitemap
   - Add Open Graph images

4. **Performance Monitoring:**
   - Web Vitals
   - Lighthouse CI

---

## Support Resources

- **Railway Docs:** https://docs.railway.app
- **Vercel Docs:** https://vercel.com/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **React Docs:** https://react.dev

For issues, check:
1. GitHub Actions logs (for data pipeline)
2. Railway/Render logs (for backend)
3. Browser console (for frontend)
4. Network tab (for API calls)

---

**Pro Tip:** Deploy to Railway first, test, then add custom domain once everything works!
