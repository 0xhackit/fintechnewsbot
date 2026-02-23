"""
Shared utilities for the fintech news pipeline.

This is the SINGLE SOURCE OF TRUTH for:
  - URL canonicalization
  - Title normalization
  - Tokenization + Jaccard similarity
  - Entity extraction + event detection
  - HTTP sessions, HTML stripping, stable IDs

All modules (dedupe.py, run_alerts.py, ai_filter.py) import from here.
"""

import os
import re
import html
import hashlib
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests
from requests.adapters import HTTPAdapter, Retry


# ===========================================================================
# HTTP / filesystem helpers
# ===========================================================================

def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def make_session(http_cfg: dict) -> requests.Session:
    total = int(http_cfg.get("retries_total", 5))
    backoff = float(http_cfg.get("backoff_factor", 0.6))
    retries = Retry(
        total=total,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def strip_html(text: str) -> str:
    if not text:
        return ""
    t = html.unescape(text)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def stable_id(canonical_url: str, title: str) -> str:
    base = f"{canonical_url}|{title.strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# ===========================================================================
# URL canonicalization (merged from utils.py + dedupe.py)
# ===========================================================================

_UTM_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_reader", "utm_referrer", "utm_social",
    "gclid", "fbclid", "mc_cid", "mc_eid",
}


def canonicalize_url(url: str) -> str:
    """
    Normalize URLs for deduplication.

    - Lowercases host, strips www.
    - Removes tracking params (UTM, gclid, fbclid, etc.)
    - Strips fragment (#)
    """
    if not url:
        return ""
    url = url.strip()
    try:
        p = urlparse(url)
        netloc = (p.netloc or "").lower().replace("www.", "")
        q = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
             if k.lower() not in _UTM_KEYS]
        query = urlencode(q, doseq=True)
        return urlunparse((p.scheme, netloc, p.path, p.params, query, ""))
    except Exception:
        return url


# ===========================================================================
# Title normalization
# ===========================================================================

# Common suffix patterns from feeds (e.g., " - Bloomberg", " | Reuters")
_OUTLET_TAIL_RE = re.compile(r"\s+[-|•]\s+[^-]{2,60}$")


def normalize_title(title: str) -> str:
    """
    Normalize a title for comparison.

    - Lowercases
    - Strips source attribution (" - Reuters", " | Bloomberg")
    - Strips common prefixes (BREAKING:, EXCLUSIVE:, etc.)
    - Strips "(Updated)" suffixes
    - Normalizes whitespace and removes non-alphanumeric chars
    """
    t = (title or "").strip().lower()
    t = _OUTLET_TAIL_RE.sub("", t)
    t = re.sub(r'^(breaking|exclusive|alert|update):\s*', '', t)
    t = re.sub(r'\s*\(updated\)$', '', t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ===========================================================================
# Tokenization + Jaccard similarity
# ===========================================================================

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "as", "by", "from", "at", "is", "are", "was", "were", "be", "been",
    "being", "it", "its", "this", "that", "these", "those", "after",
    "before", "into", "over", "under", "about", "amid", "says", "said",
    "report", "reports", "new", "will", "has", "have", "had", "not", "but",
    "than", "more", "up", "out", "also", "could", "may", "can",
}


def tokenize_title(title: str) -> set[str]:
    """
    Tokenize a title into meaningful words for Jaccard comparison.

    Uses normalize_title() first, then removes stopwords and short tokens.
    """
    t = normalize_title(title)
    # Keep / for things like 24/7
    t = re.sub(r"[^a-z0-9/\s]", " ", t)
    return {w for w in t.split() if w and w not in STOPWORDS and len(w) > 2}


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: |intersection| / |union|."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ===========================================================================
# Entity extraction + event detection
# ===========================================================================

KNOWN_ENTITIES = [
    "jpmorgan", "jp morgan", "goldman sachs", "goldman", "bank of america",
    "citigroup", "citi", "morgan stanley", "wells fargo", "hsbc",
    "barclays", "ubs", "deutsche bank", "bnp paribas", "standard chartered",
    "blackrock", "fidelity", "vanguard", "state street", "franklin templeton",
    "paypal", "visa", "mastercard", "stripe", "square", "block", "revolut",
    "wise", "plaid", "marqeta", "adyen", "checkout.com", "klarna", "affirm",
    "coinbase", "binance", "kraken", "gemini", "circle", "ripple",
    "paxos", "anchorage", "anchorage digital", "bitstamp", "bybit", "okx",
    "tether", "robinhood", "sofi", "brex",
    "cme", "cme group", "sec", "cftc", "fed", "federal reserve",
    "payoneer", "grab", "wirex",
]


def extract_entities(title: str) -> set[str]:
    """
    Extract known entities from a title.
    Returns a set of canonical (short) entity names.
    """
    t = title.lower()
    found = set()
    for entity in sorted(KNOWN_ENTITIES, key=len, reverse=True):
        if entity in t:
            found.add(entity.split()[0])
    return found


def get_event_type(title: str) -> str | None:
    """
    Determine the event type from a title.
    Returns: 'launch', 'funding', 'acquisition', or None
    """
    tl = title.lower()

    if any(kw in tl for kw in [
        "launch", "launches", "launched", "launching",
        "debut", "debuts", "debuted",
        "introduce", "introduces", "introduced",
        "unveil", "unveils", "unveiled",
        "release", "releases", "released",
    ]):
        return "launch"

    if any(kw in tl for kw in [
        "raises", "raised", "raise", "raising",
        "funding", "funds", "funded",
        "investment", "invests", "invested",
        "series a", "series b", "series c",
        "seed round", "round",
    ]):
        return "funding"

    if any(kw in tl for kw in [
        "acquires", "acquired", "acquisition",
        "merger", "merges", "merged",
        "buys", "bought", "purchase",
    ]):
        return "acquisition"

    return None
