"""
regions.py — deterministic region tagging (APAC / US / EU / LatAm).

Mirrors src/editorial.py: a gazetteer of boundary-aware regex signals, matched on
title (+ snippet/body). ~85% of crypto/digital-asset stories name a regulator,
payment scheme, currency, or firm that maps cleanly to a region. Multi-label
(a "JPMorgan in Singapore" story is US + APAC). Regulators / schemes / currencies
are strong signals; firm HQ is weaker. Returns [] when unresolved (a global crypto
story about a token/protocol often has no region — that's fine, it's a filter, not a gate).

Pure Python, no network, deterministic, unit-testable.
"""

import re

# UK is folded into EU for now (regulatory-adjacent). Split later if wanted.
REGION_SIGNALS: dict[str, list[str]] = {
    "US": [
        r"\bsec\b", r"\bfed\b", r"\bfederal reserve\b", r"\bocc\b", r"\bfdic\b",
        r"\bcftc\b", r"\bfincen\b", r"\bofac\b", r"\bnydfs\b",
        r"\bfednow\b", r"\bunited states\b", r"\bwashington\b",
        r"\bnew york\b", r"\bwall street\b", r"\bwhite house\b",
        r"\bcircle\b", r"\bcoinbase\b", r"\bpaxos\b", r"\bgemini\b", r"\bkraken\b",
        r"\banchorage\b", r"\bripple\b", r"\bpaypal\b", r"\brobinhood\b",
        r"\bblackrock\b", r"\bfidelity\b", r"\bjpmorgan\b", r"\bgoldman\b",
    ],
    "EU": [
        r"\becb\b", r"\beba\b", r"\besma\b", r"\bbafin\b", r"\bamf\b",
        r"\bmica\b", r"\bpsd2\b", r"\bsepa\b", r"\beuropean union\b", r"\beurozone\b",
        r"\beuro\b", r"\bfrankfurt\b", r"\bbrussels\b", r"\bparis\b", r"\bamsterdam\b",
        # UK (folded in)
        r"\bfca\b", r"\bpra\b", r"\bbank of england\b", r"\bboe\b", r"\blondon\b",
        r"\bpound\b", r"\bsterling\b",
        r"\brevolut\b", r"\bwise\b", r"\bmonzo\b", r"\bstarling\b", r"\bn26\b",
        r"\bbitpanda\b", r"\badyen\b", r"\bklarna\b", r"\bbitstamp\b",
    ],
    "APAC": [
        r"\bmas\b", r"\bhkma\b", r"\bjfsa\b", r"\brbi\b", r"\bsebi\b", r"\bpboc\b",
        r"\basic\b", r"\baustrac\b", r"\bbnm\b", r"\bbok\b",
        r"\bsingapore\b", r"\bhong kong\b", r"\bjapan\b", r"\bindia\b", r"\bchina\b",
        r"\baustralia\b", r"\bsouth korea\b", r"\bthailand\b", r"\bindonesia\b",
        r"\bphilippines\b", r"\bmalaysia\b", r"\bvietnam\b",
        r"\bupi\b", r"\bpaynow\b", r"\bpromptpay\b", r"\bduitnow\b",
        r"\bdbs\b", r"\bant group\b", r"\balipay\b", r"\bwechat\b", r"\btencent\b",
        r"\bgrab\b", r"\bpaytm\b", r"\banimoca\b", r"\bmatrixport\b", r"\bamber group\b",
    ],
    "LatAm": [
        r"\bbrazil\b", r"\bmexico\b", r"\bargentina\b", r"\bcolombia\b", r"\bchile\b",
        r"\bperu\b", r"\bbanco central do brasil\b", r"\bcnbv\b",
        r"\bpix\b", r"\bspei\b", r"\bcodi\b", r"\bbrazilian real\b", r"\bbrl\b",
        r"\bnubank\b", r"\bmercado pago\b", r"\bmercadopago\b",
        r"\bmercado libre\b", r"\bdlocal\b", r"\bbitso\b", r"\bripio\b",
        r"\bbuenbit\b", r"\bualá\b", r"\buala\b",
    ],
}

_ORDER = ["US", "EU", "APAC", "LatAm"]


def classify_region(title: str, snippet: str = "") -> dict:
    """
    Returns {"regions": [...], "primary": str|None, "source": "deterministic"}.
    Multi-label; `primary` prefers a title hit, then the region with the most hits.
    """
    title_l = (title or "").lower()
    full_l = f"{title or ''}  {snippet or ''}".lower()

    hits: dict[str, tuple[int, bool]] = {}
    for region in _ORDER:
        matched = [p for p in REGION_SIGNALS[region] if re.search(p, full_l)]
        if matched:
            in_title = any(re.search(p, title_l) for p in matched)
            hits[region] = (len(matched), in_title)

    if not hits:
        return {"regions": [], "primary": None, "source": "deterministic"}

    regions = [r for r in _ORDER if r in hits]
    # primary: title hit wins, then hit count, then fixed order (via _ORDER index)
    primary = max(regions, key=lambda r: (hits[r][1], hits[r][0], -_ORDER.index(r)))
    return {"regions": regions, "primary": primary, "source": "deterministic"}


if __name__ == "__main__":
    CASES = [
        ("SEC approves first spot ether ETF for listing", "US"),
        ("Circle launches USDC on new chain", "US"),
        ("BoE dilutes stablecoin rules with £40bn issuer limit", "EU"),
        ("Revolut secures EU banking licence", "EU"),
        ("MAS grants major payment institution licence to Coinbase Singapore", "APAC"),
        ("India's RBI pilots wholesale CBDC with DBS", "APAC"),
        ("Nubank rolls out crypto trading in Brazil via Pix", "LatAm"),
        ("Bitso partners with Mercado Pago in Mexico", "LatAm"),
        ("Bitcoin plunges 12% amid ETF outflows", None),  # global, no region
    ]
    passed = 0
    for title, expected in CASES:
        r = classify_region(title)
        ok = (r["primary"] == expected)
        passed += ok
        flag = "OK " if ok else "XX "
        print(f"{flag} primary={str(r['primary']):<6} regions={r['regions']}  {title[:60]}")
        if not ok:
            print(f"       expected={expected}")
    print(f"\n{passed}/{len(CASES)} cases passed")
    raise SystemExit(0 if passed == len(CASES) else 1)
