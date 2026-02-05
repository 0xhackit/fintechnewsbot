"""Dedupe utilities.

- hard_dedupe: exact-ish dedupe using canonical URL (preferred) else normalized title
- cluster_and_select: soft dedupe (similar titles across sources) + consensus boost

This file must export: hard_dedupe, cluster_and_select
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


# -------------------------
# URL canonicalization
# -------------------------

_UTM_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_name",
    "utm_reader",
    "utm_referrer",
    "utm_social",
    "gclid",
    "fbclid",
}


def _canonicalize_url(url: str) -> str:
    """Normalize URLs so the same story dedupes across sources."""
    if not url:
        return ""
    url = url.strip()
    try:
        p = urlparse(url)
        # Normalize host
        netloc = (p.netloc or "").lower().replace("www.", "")
        # Strip fragment
        fragment = ""
        # Remove common tracking params
        q = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _UTM_KEYS]
        query = urlencode(q, doseq=True)
        return urlunparse((p.scheme, netloc, p.path, p.params, query, fragment))
    except Exception:
        return url


# -------------------------
# Title normalization
# -------------------------

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "as",
    "by",
    "from",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "after",
    "before",
    "into",
    "over",
    "under",
    "about",
    "amid",
    "says",
    "said",
    "report",
    "reports",
}

# Common suffix patterns from feeds (e.g., " - Bloomberg", " | Reuters")
_OUTLET_TAIL_RE = re.compile(r"\s+[-|•]\s+[^-]{2,60}$")


def _title_key(title: str) -> str:
    t = (title or "").strip().lower()
    t = _OUTLET_TAIL_RE.sub("", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _tokenize(title: str) -> set[str]:
    t = _title_key(title)
    toks = [w for w in t.split() if w and w not in STOPWORDS and len(w) > 2]
    return set(toks)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# -------------------------
# Public API
# -------------------------


def hard_dedupe(items: list[dict]) -> list[dict]:
    """Hard dedupe to remove obvious duplicates.

    Preference: canonical URL if present, else normalized title.
    """
    seen: set[str] = set()
    out: list[dict] = []

    for it in items or []:
        url = (it.get("link") or it.get("url") or "").strip()
        key = _canonicalize_url(url)
        if not key:
            key = "title:" + _title_key(it.get("title") or "")

        if not key or key in seen:
            continue

        seen.add(key)
        out.append(it)

    return out


def _consensus_boost(unique_sources: int) -> int:
    # 1 source: +0, 2:+5, 3:+10, 4+:+15
    if unique_sources <= 1:
        return 0
    if unique_sources == 2:
        return 5
    if unique_sources == 3:
        return 10
    return 15


def cluster_and_select(items: list[dict], now_utc=None, sim_threshold: float = 0.65) -> list[dict]:
    """Soft dedupe across sources by clustering similar titles.

    - Similarity: Jaccard over token sets of normalized titles.
    - Consensus boost: +0/+5/+10/+15 based on unique sources in the cluster.
    - Representative: highest score, then most recent published_at.

    Returns one representative item per cluster, with:
      - consensus_boost
      - cluster_size
      - cluster_sources
      - score updated to include consensus_boost
    """
    if not items:
        return []

    enriched: list[tuple[dict, set[str]]] = [(it, _tokenize(it.get("title") or "")) for it in items]

    clusters: list[list[tuple[dict, set[str]]]] = []
    for it, tok in enriched:
        placed = False
        for cl in clusters:
            rep_tok = cl[0][1]
            if _jaccard(tok, rep_tok) >= sim_threshold:
                cl.append((it, tok))
                placed = True
                break
        if not placed:
            clusters.append([(it, tok)])

    selected: list[dict] = []

    for cl in clusters:
        members = [m for (m, _t) in cl]

        srcs = []
        for m in members:
            s = m.get("source_name") or m.get("source") or "Unknown"
            srcs.append(str(s))
        unique_sources = len(set(srcs))
        boost = _consensus_boost(unique_sources)

        def rep_key(m: dict):
            pub = m.get("published_at") or ""
            return (int(m.get("score") or 0), pub)

        rep = sorted(members, key=rep_key, reverse=True)[0]

        rep["consensus_boost"] = boost
        rep["cluster_size"] = len(members)
        rep["cluster_sources"] = sorted(set(srcs))

        rep["score"] = int(rep.get("score") or 0) + boost
        if isinstance(rep.get("score_breakdown"), dict):
            rep["score_breakdown"]["consensus_boost"] = boost
            rep["score_breakdown"]["cluster_size"] = len(members)

        selected.append(rep)

    return selected


__all__ = ["hard_dedupe", "cluster_and_select"]
