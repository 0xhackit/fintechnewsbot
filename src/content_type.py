"""
content_type.py — deterministic content-type / lane tagging.

The live pipeline's `category` comes from an LLM (Claude Haiku) and, due to a
`category`→`ai_category` key mismatch, never actually reaches feed.json (every
entry is "other"). This module is the deterministic, always-working replacement,
tuned to the lanes a crypto/digital-asset tech-worker reader wants:

    product_launch · funding · deal (partnership/M&A) · regulatory_action ·
    price_move · other  (kept "other" items are relabelled "breaking" upstream)

Also exposes `is_slop(title)` — cheap AI-slop / SEO tells to drop before anything else.

Pure Python, no network, deterministic, unit-testable.
"""

import re

# --- Lane patterns (precedence order matters; see classify_content_type) ---
FUNDING = [
    r"\brais(?:es|ed)\b.{0,25}\b(?:million|billion|round|seed|series|funding|\$|€|£)",
    r"\brais(?:es|ed)\s+(?:\$|€|£)", r"\bseed\s+round", r"\bseries\s+[a-e]\b",
    r"\bfunding\s+round", r"\bsecures?\s+(?:\$|€|£)?\s?\d", r"\bcloses?\s+(?:a\s+)?\$?\d.{0,20}round",
    r"\bvaluation\b", r"\bbacked\s+by\b.{0,20}\b(?:\$|€|£|million|billion)",
]
DEAL = [
    r"\bacquir(?:es|ed|ing)", r"\bacquisition", r"\bmerge(?:s|r|d)?\b", r"\bto\s+buy\b",
    r"\bbuys?\b", r"\bpartner(?:s|ed|ship|ships)?", r"\bteams?\s+up", r"\bjoin(?:s|ed)?\s+forces",
    r"\bintegrat(?:es|ed|ion)", r"\btakes?\s+(?:a\s+)?stake", r"\btakes?\s+over", r"\btook\s+over",
    r"\btaps?\b", r"\bselect(?:s|ed)\b",
]
PRODUCT_LAUNCH = [
    r"\blaunch(?:es|ed|ing)?", r"\brolls?\s+out", r"\brolled\s+out", r"\bunveil(?:s|ed)?",
    r"\bdebut(?:s|ed)?", r"\bgo(?:es)?\s+live", r"\bwent\s+live", r"\bintroduc(?:es|ed)",
    r"\bnow\s+(?:live|available)", r"\benabl(?:es|ed)", r"\badds?\s+support",
    r"\bexpands?\s+(?:to|into)", r"\bgoes?\s+public", r"\bfiles?\s+for\s+ipo", r"\bissu(?:es|ed|ance)",
]
REG_ACTION = [
    r"\bapprov(?:es|ed|al)", r"\bgrants?\s+(?:a\s+)?licen[sc]e", r"\blicen[sc]ed?\b",
    r"\bauthoriz(?:es|ed)", r"\bregisters?\b", r"\bcharg(?:es|ed)\b", r"\bsues?\b", r"\bsued\b",
    r"\blawsuit", r"\bfines?\b", r"\bfined\b", r"\bpenalt(?:y|ies)", r"\bsanction(?:s|ed)?",
    r"\bbans?\b", r"\bbanned\b", r"\bhalts?\b", r"\bseizes?\b", r"\brejects?\b", r"\bgreenlights?\b",
]

# --- Price-move (news-only lane) ---
CRYPTO_ASSETS = [
    r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\beth\b", r"\bsolana\b", r"\bsol\b",
    r"\bxrp\b", r"\bripple\b", r"\bbnb\b", r"\bcardano\b", r"\bada\b", r"\bdogecoin\b",
    r"\bdoge\b", r"\bavalanche\b", r"\bavax\b", r"\bpolygon\b", r"\bmatic\b", r"\btron\b",
    r"\blitecoin\b", r"\busdc\b", r"\busdt\b", r"\btether\b", r"\bether\b",
]
MOVE_VERB = [
    r"\bplunge(?:s|d)?", r"\bplummet(?:s|ed)?", r"\bsoar(?:s|ed)?", r"\btumble(?:s|d)?",
    r"\bsurge(?:s|d)?", r"\bjump(?:s|ed)?", r"\bdrop(?:s|ped)?", r"\bslump(?:s|ed)?",
    r"\brall(?:y|ies|ied)", r"\bslide(?:s|d)?", r"\bspike(?:s|d)?", r"\bcrash(?:es|ed)?",
    r"\bdip(?:s|ped)?", r"\bsink(?:s|ing)?", r"\bclimb(?:s|ed)?", r"\bfalls?\b", r"\bfell\b",
]
MAGNITUDE = [
    r"\d+(?:\.\d+)?\s*%", r"\$\d", r"record\s+high", r"all-?time\s+high", r"\bath\b",
    r"\bafter\b", r"\bon\b", r"\bamid\b", r"\bas\b",
]
# Predictions / targets are NOT price-move news — keep them out.
PRICE_SPECULATION = [
    r"\bprice\s+(?:prediction|target|analysis|forecast)", r"\bcould\s+(?:hit|reach|top)\b",
    r"\bto\s+reach\b", r"\bforecast", r"\bpredicts?\b", r"\bby\s+20\d\d\b",
]

# --- AI-slop / SEO title tells (drop) ---
SLOP_TITLE = [
    r"^\s*(?:is|are|will|should|can|why|what|how|who)\b.*\?\s*$",  # question titles
    r"\bguide\s+to\b", r"\bexplained\b", r"\bhow\s+to\b", r"\beverything\s+you\s+need\b",
    r"\btop\s+\d+\b", r"\bbest\s+\d+\b", r"\bthings?\s+to\s+know\b", r"\bhere'?s\s+why\b",
    r"\bwhat\s+to\s+know\b", r"\bultimate\s+guide\b", r"\bbeginner'?s\s+guide\b",
]

PRODUCT, FUND, DEAL_T, REG, PRICE, OTHER = (
    "product_launch", "funding", "deal", "regulatory_action", "price_move", "other")


def _hit(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0).strip()
    return None


def is_slop(title: str) -> bool:
    """Cheap AI-slop / SEO-listicle tell on the title alone."""
    return _hit(SLOP_TITLE, (title or "").lower()) is not None


def _is_price_move(title_l: str, full_l: str) -> str | None:
    if _hit(PRICE_SPECULATION, title_l):
        return None
    if not _hit(CRYPTO_ASSETS, title_l):
        return None
    verb = _hit(MOVE_VERB, title_l)
    if not verb:
        return None
    if not _hit(MAGNITUDE, title_l):
        return None
    return verb


def classify_content_type(title: str, snippet: str = "") -> dict:
    """
    Returns {"content_type": str, "matched": str|None}.
    Precedence: funding → deal → product_launch → regulatory_action → price_move → other.
    Lane decisions are judged on the TITLE (snippet is noisy).
    """
    title_l = (title or "").lower()
    full_l = f"{title or ''}  {snippet or ''}".lower()

    m = _hit(FUNDING, title_l)
    if m:
        return {"content_type": FUND, "matched": m}
    m = _hit(DEAL, title_l)
    if m:
        return {"content_type": DEAL_T, "matched": m}
    m = _hit(PRODUCT_LAUNCH, title_l)
    if m:
        return {"content_type": PRODUCT, "matched": m}
    m = _hit(REG_ACTION, title_l)
    if m:
        return {"content_type": REG, "matched": m}
    m = _is_price_move(title_l, full_l)
    if m:
        return {"content_type": PRICE, "matched": m}
    return {"content_type": OTHER, "matched": None}


if __name__ == "__main__":
    CASES = [
        ("Midas raises $50 million Series A for tokenized assets", FUND),
        ("Stripe acquires Bridge for $1.1 billion", DEAL_T),
        ("Circle partners with Visa to enable USDC settlement", DEAL_T),
        ("JPMorgan launches blockchain deposit token", PRODUCT),
        ("Nium rolls out stablecoin card issuance platform", PRODUCT),
        ("SEC approves first spot ether ETF", REG),
        ("SEC sues Binance over unregistered securities", REG),
        ("Bitcoin plunges 12% amid ETF outflows", PRICE),
        ("Ethereum soars 8% after Dencun upgrade", PRICE),
        ("Bitcoin price prediction: BTC could hit $200k by 2027", OTHER),  # speculation, not price-move
        ("Coinbase reports record quarterly volume", OTHER),
    ]
    passed = 0
    for title, expected in CASES:
        r = classify_content_type(title)
        ok = r["content_type"] == expected
        passed += ok
        flag = "OK " if ok else "XX "
        print(f"{flag} {r['content_type']:<18} {title[:58]}")
        if not ok:
            print(f"       expected={expected}  matched={r['matched']}")
    slop_cases = [
        ("Is Bitcoin the future of money?", True),
        ("Top 10 stablecoins to watch in 2026", True),
        ("A beginner's guide to tokenization", True),
        ("Circle launches USDC on Base", False),
    ]
    for title, expected in slop_cases:
        ok = is_slop(title) == expected
        passed += ok
        flag = "OK " if ok else "XX "
        print(f"{flag} slop={is_slop(title)!s:<5} {title[:58]}")
    total = len(CASES) + len(slop_cases)
    print(f"\n{passed}/{total} cases passed")
    raise SystemExit(0 if passed == total else 1)
