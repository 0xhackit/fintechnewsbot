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
import json
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
    # Iteratively strip trailing source attributions (up to 5 passes)
    # e.g. "Article - Source A - Source B" → "Article"
    for _ in range(5):
        stripped = _OUTLET_TAIL_RE.sub("", t)
        if stripped == t:
            break
        t = stripped
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
    "northern trust", "bny mellon", "nomura", "mizuho",
    "dbs", "hashkey", "amber group",
]

# Cache for merged entity list (KNOWN_ENTITIES + config.json digital_asset_banks)
_ALL_ENTITIES_CACHE: list[str] | None = None


def _load_all_entities() -> list[str]:
    """Load and merge entities from KNOWN_ENTITIES + config.json digital_asset_banks.

    Cached after first call.  Falls back to KNOWN_ENTITIES if config is missing.
    """
    global _ALL_ENTITIES_CACHE
    if _ALL_ENTITIES_CACHE is not None:
        return _ALL_ENTITIES_CACHE

    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        config_banks = cfg.get("digital_asset_banks", [])
        config_lower = [b.strip().lower() for b in config_banks if b.strip()]
    except Exception:
        config_lower = []

    # Merge: KNOWN_ENTITIES + config banks, deduplicated
    merged = list(KNOWN_ENTITIES)
    existing_lower = {e.lower() for e in merged}
    for entity in config_lower:
        if entity not in existing_lower:
            merged.append(entity)
            existing_lower.add(entity)

    _ALL_ENTITIES_CACHE = merged
    return _ALL_ENTITIES_CACHE


# ---------------------------------------------------------------------------
# Dynamic proper noun extraction (list-free entity detection)
# ---------------------------------------------------------------------------

# Verbs that typically start the action clause in a news headline.
# Used to split title-case headlines into [ENTITY] [VERB] [REST].
_HEADLINE_VERBS = {
    # Launch/release
    "launch", "launches", "launched", "launching",
    "debut", "debuts", "debuted",
    "introduce", "introduces", "introduced",
    "unveil", "unveils", "unveiled",
    "release", "releases", "released",
    "rollout", "rolls",
    # Funding/deals
    "raise", "raises", "raised", "raising",
    "secure", "secures", "secured",
    # Partnerships/moves
    "partner", "partners", "partnered",
    "join", "joins", "joined",
    "sign", "signs", "signed",
    "tap", "taps", "tapped",
    "hire", "hires", "hired",
    "name", "names", "named",
    # Market actions
    "acquire", "acquires", "acquired",
    "buy", "buys", "bought",
    "sell", "sells", "sold",
    "expand", "expands", "expanded",
    "enter", "enters", "entered",
    "target", "targets", "targeted",
    "plan", "plans", "planned",
    "explore", "explores", "explored",
    "eye", "eyes", "eyed",
    "seek", "seeks", "sought",
    "back", "backs", "backed",
    "add", "adds", "added",
    "file", "files", "filed",
    "report", "reports", "reported",
    "say", "says", "said",
    "reveal", "reveals", "revealed",
    "announce", "announces", "announced",
    # Prepositions / auxiliaries (mark end of entity in title-case)
    "to", "in", "is", "are", "was", "were",
    "has", "have", "had", "will", "may", "could",
}

_CONNECTING_WORDS = {"of", "and", "the", "for", "&", "de", "du", "van"}


def extract_proper_nouns(title: str) -> set[str]:
    """Extract 2-word proper noun phrases from a title dynamically.

    Works for both sentence-case and title-case titles without relying
    on a predefined entity list.

    Sentence case: finds consecutive capitalized word sequences.
    Title case: takes words before the first headline verb.
    Returns the first 2 capitalized words of each detected sequence,
    lowercased.

    Examples:
        "Northern Trust Asset Management launches tokenized MMF"
            → {"northern trust"}
        "Northern Trust Launches Tokenized Treasury Fund"
            → {"northern trust"}
        "SEC says regulation coming"
            → set()   (single-word — handled by KNOWN_ENTITIES instead)
    """
    words = (title or "").strip().split()
    if len(words) < 2:
        return set()

    phrases: set[str] = set()
    cap_count = sum(1 for w in words if w[:1].isupper())
    is_title_case = cap_count / len(words) > 0.6

    if is_title_case:
        # Title case: entity = capitalized words before the first headline verb
        entity_words: list[str] = []
        for w in words:
            if w.lower().rstrip(".,;:'\"!?") in _HEADLINE_VERBS:
                break
            if w[:1].isupper():
                entity_words.append(w)
        if len(entity_words) >= 2:
            phrases.add(f"{entity_words[0]} {entity_words[1]}".lower())
    else:
        # Sentence case: find consecutive capitalized word sequences
        i = 0
        while i < len(words):
            w = words[i]
            if w[:1].isupper() and w.lower() not in _CONNECTING_WORDS:
                seq = [w]
                j = i + 1
                while j < len(words):
                    wj = words[j]
                    if wj[:1].isupper() or wj.lower() in _CONNECTING_WORDS:
                        seq.append(wj)
                        j += 1
                    else:
                        break
                # Take first 2 capitalized words as entity identifier
                cap_words = [s for s in seq if s[:1].isupper()]
                if len(cap_words) >= 2:
                    phrases.add(f"{cap_words[0]} {cap_words[1]}".lower())
                i = j if j > i + 1 else i + 1
            else:
                i += 1

    return phrases


def extract_entities(title: str) -> set[str]:
    """
    Extract entities from a title.

    Two complementary methods:
      1. List-based: matches against KNOWN_ENTITIES + config.json digital_asset_banks
         (catches single-word entities like "SEC", "Coinbase")
      2. Dynamic: extracts multi-word proper nouns from capitalization patterns
         (catches ANY institution: "Northern Trust", "Alliant Credit Union", etc.)

    Returns a set of canonical (short) entity names.
    """
    # Method 1: List-based matching (existing)
    all_entities = _load_all_entities()
    t = title.lower()
    found = set()
    for entity in sorted(all_entities, key=len, reverse=True):
        if entity in t:
            found.add(entity.split()[0])

    # Method 2: Dynamic proper noun extraction (catches ANY multi-word institution)
    for noun_phrase in extract_proper_nouns(title):
        found.add(noun_phrase.split()[0])

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
