"""Dedupe utilities.

- hard_dedupe: exact-ish dedupe using canonical URL (preferred) else normalized title
- cluster_and_select: soft dedupe (similar titles across sources) + consensus boost

This file must export: hard_dedupe, cluster_and_select
"""

from __future__ import annotations

from .utils import canonicalize_url, normalize_title, tokenize_title, jaccard_similarity


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
        key = canonicalize_url(url)
        if not key:
            key = "title:" + normalize_title(it.get("title") or "")

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

    enriched: list[tuple[dict, set[str]]] = [(it, tokenize_title(it.get("title") or "")) for it in items]

    clusters: list[list[tuple[dict, set[str]]]] = []
    for it, tok in enriched:
        placed = False
        for cl in clusters:
            rep_tok = cl[0][1]
            if jaccard_similarity(tok, rep_tok) >= sim_threshold:
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
