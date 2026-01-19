from typing import List, Dict, Any
import re


def _build_patterns(keywords: List[str]):
    phrases = []
    word_pats = []
    for kw in keywords or []:
        k = (kw or "").strip()
        if not k:
            continue
        if " " in k:
            phrases.append((kw, k.casefold()))
        else:
            word_pats.append((kw, re.compile(rf"\b{re.escape(k.casefold())}\b")))
    return phrases, word_pats


def _match_keywords(text: str, phrases, word_pats) -> List[str]:
    t = (text or "").casefold()
    hits = []
    for orig, folded in phrases:
        if folded in t:
            hits.append(orig)
    for orig, pat in word_pats:
        if pat.search(t):
            hits.append(orig)
    # dedupe preserve order
    seen = set()
    out = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def match_item(item: Dict[str, Any], keywords: List[str], topics: List[Dict[str, Any]]) -> Dict[str, Any]:
    title = item.get("title") or ""
    snippet = item.get("snippet") or ""
    blob = f"{title}\n{snippet}"

    phrases, word_pats = _build_patterns(keywords)
    matched_kw = _match_keywords(blob, phrases, word_pats)

    matched_topics = []
    blob_folded = blob.casefold()
    for t in topics or []:
        name = t.get("name")
        any_terms = t.get("any", [])
        if not name or not any_terms:
            continue
        for term in any_terms:
            if (term or "").casefold() in blob_folded:
                matched_topics.append(name)
                break

    item["matched_keywords"] = matched_kw
    item["matched_topics"] = matched_topics
    return item