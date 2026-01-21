# Fintech News Terminal - Web Application

A Bloomberg-style real-time news terminal for fintech, stablecoins, RWA, and tokenization news.

## Features

- **Real-time News Feed** - Auto-refreshes every 5 minutes
- **Category Filtering** - Filter by Stablecoins, RWA, Fintech, Tokenization, Launches, Funding
- **Score-based Ranking** - High-priority stories highlighted
- **Bloomberg-style Dark Theme** - Professional terminal aesthetics
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Live Stats Dashboard** - Analytics on score distribution and sources

## Architecture

### Backend (FastAPI)
- **Location**: `api/main.py`
- **Port**: 8000
- **Endpoints**:
  - `GET /` - Health check
  - `GET /api/news` - Get news with filtering (category, min_score, limit)
  - `GET /api/categories` - Get all categories with counts
  - `GET /api/stats` - Get feed statistics
  - `GET /api/health` - Detailed health check

### Frontend (React + Vite)
- **Location**: `frontend/`
- **Port**: 3000 (development)
- **Stack**: React 18, Vite 6, Axios, date-fns
- **Styling**: Custom CSS with Bloomberg-inspired design system

### Data Flow
```
GitHub Actions (every 5 min)
  ↓
out/items_last24h.json (updated)
  ↓
FastAPI Backend (reads JSON, adds categories)
  ↓
React Frontend (fetches via API, auto-refreshes)
```

## Local Development

### Prerequisites
- Python 3.12+
- Node.js 18+
- npm or yarn

### Step 1: Start Backend

```bash
# Navigate to project root
cd fintech-news-mvp

# Install backend dependencies
pip install -r api/requirements.txt

# Start FastAPI server
python api/main.py
# or
uvicorn api.main:app --reload --port 8000
```

Backend will be available at http://localhost:8000

### Step 2: Start Frontend

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at http://localhost:3000

### Step 3: Test API

```bash
# Check health
curl http://localhost:8000/

# Get news
curl http://localhost:8000/api/news

# Get categories
curl http://localhost:8000/api/categories

# Get stats
curl http://localhost:8000/api/stats

# Filter by category
curl "http://localhost:8000/api/news?category=Stablecoins"

# Filter by minimum score
curl "http://localhost:8000/api/news?min_score=35"
```

## Production Deployment

### Option 1: Railway (Recommended)

**Backend Deployment:**
1. Fork/clone the repo
2. Push to GitHub
3. Create new project on [Railway](https://railway.app)
4. Connect your GitHub repo
5. Railway will auto-detect Dockerfile
6. Deploy! Your API will be at `https://your-app.railway.app`

**Frontend Deployment:**
1. Build frontend:
   ```bash
   cd frontend
   npm run build
   ```
2. Deploy `dist/` folder to:
   - Vercel: `vercel deploy`
   - Netlify: Drag and drop `dist/` folder
   - Cloudflare Pages: Connect GitHub repo

3. Update frontend `.env`:
   ```bash
   VITE_API_URL=https://your-app.railway.app/api
   ```

### Option 2: Render

**Backend:**
1. Create new Web Service on [Render](https://render.com)
2. Connect GitHub repo
3. Set:
   - Build Command: `pip install -r api/requirements.txt`
   - Start Command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
4. Deploy!

**Frontend:** Same as Railway Option

### Option 3: Docker Compose (Self-hosted)

```yaml
# docker-compose.yml
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

  frontend:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
    depends_on:
      - backend
    restart: unless-stopped
```

```bash
docker-compose up -d
```

## Configuration

### Backend Environment Variables

No environment variables required! The backend reads directly from:
- `out/items_last24h.json` - News data (updated by GitHub Actions)
- `config.json` - Configuration

### Frontend Environment Variables

Create `frontend/.env`:

```bash
# Development
VITE_API_URL=http://localhost:8000/api

# Production
VITE_API_URL=https://your-backend.railway.app/api
```

## Category Mapping

The backend automatically categorizes items based on matched topics and keywords:

| Category | Criteria |
|----------|----------|
| **Stablecoins** | Topics: "Stablecoin adoption"<br>Keywords: stablecoin, usdc, usdt, tether, circle |
| **RWA** | Topics: "Tokenized funds & RWA"<br>Keywords: rwa, tokenized treasury, fund |
| **Fintech** | Topics: "Crypto-native fintech launches"<br>Keywords: fintech, payments, neobank |
| **Tokenization** | Keywords: tokenization, tokenized |
| **Launches** | Keywords: launch, partnership, unveils |
| **Funding** | Keywords: funding, raises, series a/b/c |

## API Response Examples

### GET /api/news

```json
{
  "total": 45,
  "items": [
    {
      "title": "Circle Launches USDC on Solana",
      "link": "https://...",
      "published_at": "2026-01-21T10:30:00Z",
      "source": "coindesk",
      "source_type": "rss",
      "score": 45,
      "score_breakdown": {
        "tier1": 1,
        "tier2": 1,
        "freshness": 10,
        ...
      },
      "matched_topics": ["Stablecoin adoption"],
      "matched_keywords": ["stablecoin", "usdc", "launch"],
      "categories": ["Stablecoins", "Launches"],
      "snippet": "Circle announced today..."
    }
  ],
  "timestamp": "2026-01-21T12:00:00Z"
}
```

### GET /api/categories

```json
{
  "categories": [
    {"name": "Stablecoins", "count": 18},
    {"name": "RWA", "count": 12},
    {"name": "Fintech", "count": 10},
    {"name": "Launches", "count": 8},
    {"name": "Funding", "count": 5}
  ],
  "timestamp": "2026-01-21T12:00:00Z"
}
```

## Customization

### Adding New Categories

Edit `api/main.py`, `categorize_item()` function:

```python
def categorize_item(item: dict) -> List[str]:
    categories = set()

    # Add your custom category logic
    if "defi" in item.get("matched_keywords", []):
        categories.add("DeFi")

    return sorted(list(categories))
```

### Changing Color Scheme

Edit `frontend/src/index.css`:

```css
:root {
  --accent-blue: #your-color;
  --accent-green: #your-color;
  ...
}
```

### Adjusting Auto-refresh Interval

Edit `frontend/src/App.jsx`:

```javascript
// Change from 5 minutes to 2 minutes
const interval = setInterval(() => {
  fetchNews();
}, 2 * 60 * 1000); // 2 minutes
```

## Performance

- **Backend**: Handles 1000+ req/sec on standard Railway instance
- **Data Size**: ~2-5 MB JSON (200-500 news items)
- **Load Time**: < 2 seconds initial load
- **Auto-refresh**: 5 minutes (configurable)

## Troubleshooting

### Backend Not Starting

```bash
# Check if port 8000 is available
lsof -i :8000

# Check if out/items_last24h.json exists
ls -l out/items_last24h.json

# Run with verbose logging
uvicorn api.main:app --reload --log-level debug
```

### Frontend CORS Errors

Add your frontend domain to backend CORS whitelist in `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-frontend.vercel.app"
    ],
    ...
)
```

### No Data Showing

1. Ensure GitHub Actions pipeline is running (check Actions tab)
2. Verify `out/items_last24h.json` has data
3. Check backend logs for errors
4. Test API directly: `curl http://localhost:8000/api/news`

## Security Considerations

- **CORS**: Update `allow_origins` in production
- **Rate Limiting**: Add rate limiting middleware for public deployments
- **API Keys**: Not required for read-only endpoints
- **HTTPS**: Always use HTTPS in production (Railway/Vercel provide this)

## Future Enhancements

- [ ] WebSocket support for real-time updates
- [ ] Search functionality
- [ ] Bookmarking/favorites
- [ ] Email digest subscriptions
- [ ] Advanced filtering (date range, multiple categories)
- [ ] Export to CSV/PDF
- [ ] Dark/Light theme toggle
- [ ] Multi-language support

## Support

For issues or questions:
1. Check GitHub Actions logs
2. Test API endpoints directly
3. Review browser console for frontend errors
4. Check backend logs with `--log-level debug`
