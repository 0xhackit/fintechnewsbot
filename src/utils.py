import os
import re
import html
import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from requests.adapters import HTTPAdapter, Retry


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


_TRACKING_KEYS_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"gclid", "fbclid", "mc_cid", "mc_eid"}


def canonicalize_url(url: str) -> str:
    """
    Remove tracking params + fragments. Keep scheme/netloc/path + filtered query.
    """
    if not url:
        return ""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)

    filtered = []
    for k, v in query:
        lk = (k or "").lower()
        if any(lk.startswith(p) for p in _TRACKING_KEYS_PREFIXES):
            continue
        if lk in _TRACKING_KEYS:
            continue
        filtered.append((k, v))

    new_query = urlencode(filtered, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, ""))


def stable_id(canonical_url: str, title: str) -> str:
    base = f"{canonical_url}|{title.strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()