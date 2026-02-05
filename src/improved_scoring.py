"""
Improved scoring system with institution weighting, financial impact, and regulatory priority.

This module provides enhanced scoring that:
1. Prioritizes major financial institutions and regulators
2. Boosts stories with significant financial amounts ($X billion)
3. Elevates regulatory/policy news
4. Reduces commentary penalty for institutional sources
5. Maintains hard rejects for listicles and generic content
"""

import re
from datetime import datetime


# Major financial institutions (priority sources)
TIER1_INSTITUTIONS = [
    "jpmorgan", "jp morgan", "goldman sachs", "goldman", "bank of america", "bofa",
    "citibank", "citi", "citigroup", "morgan stanley", "wells fargo",
    "hsbc", "barclays", "ubs", "credit suisse", "deutsche bank",
    "bnp paribas", "societe generale", "standard chartered",
    "fidelity", "blackrock", "vanguard", "state street", "pimco",
    "paypal", "visa", "mastercard", "stripe", "square", "block", "revolut",
    "checkout.com", "adyen", "wise", "plaid"
]

# Crypto-native institutions
TIER2_INSTITUTIONS = [
    "coinbase", "binance", "kraken", "gemini", "circle", "ripple",
    "paxos", "anchorage", "bitstamp", "bitfinex", "bybit", "okx",
    "tether", "usdc"
]

# Regulators and central banks (highest priority)
REGULATORS = [
    "sec", "securities and exchange", "federal reserve", "fed", "treasury",
    "fdic", "occ", "comptroller of the currency", "cftc",
    "central bank", "ecb", "european central bank", "bank of england",
    "monetary authority", "financial authority", "securities commission",
    "finra", "financial conduct authority", "fca", "esma", "mifid",
    "peoples bank of china", "pboc", "reserve bank", "bank negara"
]

# Regulatory action keywords
REGULATORY_KEYWORDS = [
    "approval", "approves", "approved", "authorizes", "authorized", "authorization",
    "regulation", "regulatory", "compliance", "compliant", "licensed", "licensing",
    "guidance", "ruling", "rules", "rule", "law", "legislation", "legislative",
    "sanctions", "sanctioned", "enforcement", "investigation", "investigates",
    "permits", "permitted", "permission", "clears", "cleared", "greenlight"
]

# Financial impact patterns (pattern, bonus_points)
FINANCIAL_PATTERNS = [
    (r'\$\d+\s*trillion', 50),       # "$2 trillion"
    (r'\d+\s*trillion', 50),         # "2 trillion"
    (r'\$\d+\s*billion', 40),        # "$500 billion"
    (r'\d+\s*billion', 40),          # "500 billion"
    (r'\$\d+\.?\d*\s*bn', 40),       # "$5.2bn"
    (r'\d+\.?\d*\s*bn', 40),         # "5.2bn"
    (r'\$\d{3,}\s*million', 30),     # "$100 million"
    (r'\d{3,}\s*million', 30),       # "100 million"
    (r'\$\d+\.?\d*\s*mn', 30),       # "$50mn"
]


def get_institution_bonus(item: dict) -> int:
    """Calculate bonus points for institutional sources."""
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()

    # Regulator mention = +30 points (highest priority)
    if any(reg in text for reg in REGULATORS):
        return 30

    # Tier 1 institution (major banks/fintech) = +20 points
    if any(inst in text for inst in TIER1_INSTITUTIONS):
        return 20

    # Tier 2 institution (crypto-native) = +10 points
    if any(inst in text for inst in TIER2_INSTITUTIONS):
        return 10

    return 0


def get_financial_impact_bonus(item: dict) -> int:
    """Calculate bonus for significant financial amounts."""
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()

    for pattern, bonus in FINANCIAL_PATTERNS:
        if re.search(pattern, text):
            return bonus

    return 0


def get_regulatory_bonus(item: dict) -> int:
    """Calculate bonus for regulatory/policy news."""
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    title = item.get('title', '').lower()

    # Regulator in title + regulatory keyword = +40 (critical regulatory action)
    if any(reg in title for reg in REGULATORS):
        if any(kw in text for kw in REGULATORY_KEYWORDS):
            return 40

    # Just regulatory keywords in text = +15
    if any(kw in text for kw in REGULATORY_KEYWORDS):
        return 15

    return 0


def get_commentary_penalty(item: dict, comm_count: int) -> int:
    """Calculate commentary penalty (reduced for institutional sources)."""
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()

    # Check if from major institution or regulator
    has_institution = (
        any(inst in text for inst in TIER1_INSTITUTIONS) or
        any(reg in text for reg in REGULATORS)
    )

    if has_institution:
        # Institutional commentary is valuable (-10 per keyword, max -30)
        return -min(comm_count * 10, 30)
    else:
        # Generic commentary is noise (-20 per keyword, max -50)
        return -min(comm_count * 20, 50)


def score_item_improved(item: dict, now_utc: datetime,
                       tier1_count: int, tier2_count: int, comm_count: int,
                       listicle_count: int, generic_count: int) -> dict:
    """
    Enhanced scoring with institution weighting and financial impact.

    Args:
        item: Item dict with title, snippet, etc.
        now_utc: Current time for freshness calculation
        tier1_count: Count of tier 1 launch patterns
        tier2_count: Count of tier 2 activity patterns
        comm_count: Count of commentary patterns
        listicle_count: Count of listicle patterns
        generic_count: Count of generic patterns

    Returns:
        Item dict with 'score' and 'score_breakdown' fields added
    """
    source_type = item.get('source_type', '')

    # Base launch score (same as before)
    launch_score = min(tier1_count * 25, 60) + min(tier2_count * 10, 30)

    # NEW: Context-aware bonuses
    institution_bonus = get_institution_bonus(item)
    financial_bonus = get_financial_impact_bonus(item)
    regulatory_bonus = get_regulatory_bonus(item)

    # Commentary penalty (reduced for institutional sources)
    commentary_penalty = get_commentary_penalty(item, comm_count)

    # Quality penalties (unchanged)
    listicle_penalty = -min(listicle_count * 100, 200)
    generic_penalty = -min(generic_count * 50, 100)

    # Source penalty (unchanged)
    source_penalty = -15 if source_type == 'telegram' else 0

    # Freshness (unchanged)
    freshness = 0
    try:
        if item.get("published_at"):
            dt = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            hours = (now_utc - dt).total_seconds() / 3600
            if hours <= 6:
                freshness = 10
            elif hours <= 24:
                freshness = 4
    except Exception:
        pass

    # TOTAL SCORE
    score = (
        launch_score +
        institution_bonus +
        financial_bonus +
        regulatory_bonus +
        commentary_penalty +
        listicle_penalty +
        generic_penalty +
        source_penalty +
        freshness
    )

    # Smart overrides
    # 1. Major institution + any tier1/tier2 activity = minimum 40 points
    if institution_bonus >= 20 and (tier1_count >= 1 or tier2_count >= 1):
        score = max(score, 40)

    # 2. Regulator + regulatory keyword = minimum 50 points
    if regulatory_bonus >= 40:
        score = max(score, 50)

    # 3. Financial impact ($XB) + institution = minimum 45 points
    if financial_bonus >= 30 and institution_bonus >= 10:
        score = max(score, 45)

    # 4. Central bank + stablecoin/tokenized = minimum 50 points
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    has_central_bank = any(cb in text for cb in ["central bank", "monetary authority"])
    has_crypto = any(kw in text for kw in ["stablecoin", "tokenized", "tokenization", "cbdc"])
    if has_central_bank and has_crypto:
        score = max(score, 50)

    # Hard rejects (unchanged)
    # Hard reject listicles and generic content
    if listicle_count >= 1 or generic_count >= 1:
        score = min(score, -50)

    # Suppress heavy commentary without substance
    if comm_count >= 2 and tier1_count == 0 and tier2_count == 0 and institution_bonus == 0:
        score = min(score, 10)

    # Ensure basic launch with tier1 gets minimum score
    if tier1_count >= 1 and comm_count <= 1 and listicle_count == 0 and generic_count == 0:
        score = max(score, 35)

    item["score"] = int(score)
    item["score_breakdown"] = {
        "tier1": tier1_count,
        "tier2": tier2_count,
        "commentary": comm_count,
        "listicle": listicle_count,
        "generic": generic_count,
        "freshness": freshness,
        "source_penalty": source_penalty,
        "launch_score": launch_score,
        "institution_bonus": institution_bonus,
        "financial_bonus": financial_bonus,
        "regulatory_bonus": regulatory_bonus,
        "commentary_penalty": commentary_penalty,
        "listicle_penalty": listicle_penalty,
        "generic_penalty": generic_penalty,
    }
    return item
