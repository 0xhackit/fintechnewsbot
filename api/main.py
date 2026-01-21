#!/usr/bin/env python3
"""
FastAPI backend for fintech news terminal.
Serves news data with real-time updates and category filtering.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import json
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

app = FastAPI(title="Fintech News Terminal API", version="1.0.0")

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://fintech-news-terminal.vercel.app",   # Vercel deployments
        "*"                       # Allow all (can restrict later)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data paths
ITEMS_PATH = Path("out/items_last24h.json")
CONFIG_PATH = Path("config.json")


class NewsItem(BaseModel):
    title: str
    link: str
    published_at: Optional[str]
    source: str
    source_type: str
    score: int
    score_breakdown: dict
    matched_topics: List[str]
    matched_keywords: List[str]
    snippet: Optional[str] = None
    categories: List[str]  # New: derived from matched_topics


def load_json(path: Path, default=None):
    """Load JSON file with error handling."""
    if not path.exists():
        return default if default is not None else []
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return default if default is not None else []


def categorize_item(item: dict) -> List[str]:
    """
    Derive categories from matched topics and keywords.
    Maps topics to clean category labels.
    """
    categories = set()

    # Map topics to category labels
    topic_map = {
        "Stablecoin adoption": "Stablecoins",
        "Tokenized funds & RWA": "RWA",
        "Crypto-native fintech launches": "Fintech",
    }

    for topic in item.get("matched_topics", []):
        if topic in topic_map:
            categories.add(topic_map[topic])

    # Add keyword-based categories
    keywords = [kw.lower() for kw in item.get("matched_keywords", [])]

    if any(kw in keywords for kw in ["tokenization", "tokenized", "rwa"]):
        categories.add("Tokenization")

    if any(kw in keywords for kw in ["stablecoin", "usdc", "usdt", "tether", "circle"]):
        categories.add("Stablecoins")

    if any(kw in keywords for kw in ["funding", "raises", "series a", "series b"]):
        categories.add("Funding")

    # Regulation category for regulatory news
    if any(kw in keywords for kw in ["mica", "genius", "stablecoin bill", "regulation", "regulatory", "sec", "cftc", "compliance"]):
        categories.add("Regulation")

    # No default category - items without matches won't be shown

    return sorted(list(categories))


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Fintech News Terminal API",
        "version": "1.0.0",
        "endpoints": {
            "news": "/api/news",
            "categories": "/api/categories",
            "stats": "/api/stats",
        }
    }


@app.get("/api/news")
def get_news(
    category: Optional[str] = None,
    min_score: Optional[int] = None,
    limit: Optional[int] = None,
):
    """
    Get news items with optional filtering.

    Query params:
    - category: Filter by category (Stablecoins, RWA, Fintech, etc.)
    - min_score: Minimum score threshold
    - limit: Maximum number of items to return
    """
    items = load_json(ITEMS_PATH, [])

    if not isinstance(items, list):
        raise HTTPException(status_code=500, detail="Invalid data format")

    # Add categories to each item
    for item in items:
        item["categories"] = categorize_item(item)

    # Apply filters
    if category:
        items = [item for item in items if category in item.get("categories", [])]

    if min_score is not None:
        items = [item for item in items if item.get("score", 0) >= min_score]

    # Sort by score (desc) and published_at (desc)
    items.sort(
        key=lambda x: (x.get("score", 0), x.get("published_at") or ""),
        reverse=True
    )

    # Apply limit
    if limit:
        items = items[:limit]

    return {
        "total": len(items),
        "items": items,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/categories")
def get_categories():
    """Get list of all available categories with counts."""
    items = load_json(ITEMS_PATH, [])

    if not isinstance(items, list):
        raise HTTPException(status_code=500, detail="Invalid data format")

    # Add categories to each item and count
    category_counts = {}
    for item in items:
        categories = categorize_item(item)
        for cat in categories:
            category_counts[cat] = category_counts.get(cat, 0) + 1

    # Sort by count (desc)
    categories = sorted(
        [{"name": cat, "count": count} for cat, count in category_counts.items()],
        key=lambda x: x["count"],
        reverse=True
    )

    return {
        "categories": categories,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/stats")
def get_stats():
    """Get overall statistics about the news feed."""
    items = load_json(ITEMS_PATH, [])
    config = load_json(CONFIG_PATH, {})

    if not isinstance(items, list):
        raise HTTPException(status_code=500, detail="Invalid data format")

    # Calculate stats
    total_items = len(items)

    # Score distribution
    high_score = len([i for i in items if i.get("score", 0) >= 35])
    medium_score = len([i for i in items if 20 <= i.get("score", 0) < 35])
    low_score = len([i for i in items if i.get("score", 0) < 20])

    # Source type distribution
    source_types = {}
    for item in items:
        st = item.get("source_type", "unknown")
        source_types[st] = source_types.get(st, 0) + 1

    # Category distribution
    category_counts = {}
    for item in items:
        categories = categorize_item(item)
        for cat in categories:
            category_counts[cat] = category_counts.get(cat, 0) + 1

    # Recent items (last 6 hours)
    now = datetime.now(timezone.utc)
    recent_items = []
    for item in items:
        pub = item.get("published_at")
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                hours_ago = (now - dt).total_seconds() / 3600
                if hours_ago <= 6:
                    recent_items.append(item)
            except Exception:
                pass

    return {
        "total_items": total_items,
        "score_distribution": {
            "high": high_score,
            "medium": medium_score,
            "low": low_score,
        },
        "source_types": source_types,
        "categories": category_counts,
        "recent_count": len(recent_items),
        "lookback_hours": config.get("lookback_hours", 24),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/health")
def health_check():
    """Detailed health check."""
    items_exist = ITEMS_PATH.exists()
    config_exist = CONFIG_PATH.exists()

    return {
        "status": "healthy" if items_exist else "degraded",
        "data_file_exists": items_exist,
        "config_file_exists": config_exist,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
