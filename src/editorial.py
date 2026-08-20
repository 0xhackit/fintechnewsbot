"""
editorial.py — "market event vs. commentary/policy" editorial policy.

This adds the one axis the broad pipeline is missing: is a story a CONCRETE
MARKET EVENT — a named actor doing a discrete thing (launch, deal, funding,
integration, acquisition, go-live, or a concrete regulatory ACTION like an
approval / licence / lawsuit / fine) — versus COMMENTARY/OPINION (framing,
speculation, op-eds, "X casts Y as Z", "race to define"), POLICY NOISE
(rule-making, proposals, consultations, "issuer limits" that are not yet a
concrete action), POLITICAL noise (senators, PACs, elections), or LOW-SIGNAL
stat/promo pieces ("market cap rises 40%").

The "market" profile keeps concrete market events (incl. concrete regulatory
ACTIONS — per the chosen policy: keep only concrete actions) and kills
commentary + policy noise + political + low-signal.

Pure Python, no network, deterministic, unit-testable. The shadow runner
(scripts/shadow_market.py) uses this to produce a side-by-side KEPT/KILLED
report without touching the live pipeline.

Decision precedence (first match wins):
    1. POLITICAL  → kill        (unless a hard market deal is also present)
    2. concrete REG ACTION → keep  (approval / licence / charge / fine / ban)
    3. COMMENTARY → kill        (unless a strong concrete event is present)
    4. POLICY noise → kill
    5. LOW-SIGNAL → kill        (unless any market-event verb is present)
    6. any MARKET EVENT → keep
    7. otherwise → review       (genuinely ambiguous; surfaced, not silently dropped)
"""

import re

# ---------------------------------------------------------------------------
# Pattern banks
# ---------------------------------------------------------------------------

# Strong, unambiguous market-event verbs. Presence of one of these overrides
# soft commentary framing ("Visa says it will *launch* ...").
STRONG_EVENT = [
    r"\blaunch(?:es|ed|ing)?", r"\bunveil(?:s|ed|ing)?", r"\brolls?\s+out", r"\brolled\s+out",
    r"\bdebut(?:s|ed)?", r"\bgo(?:es)?\s+live", r"\bwent\s+live", r"\bgoes?\s+public",
    r"\bpartner(?:s|ed|ship|ships)?", r"\bteams?\s+up", r"\bjoin(?:s|ed)?\s+forces",
    r"\bacquir(?:es|ed|ing)", r"\bacquisition", r"\bto\s+buy\b", r"\bbuys?\b", r"\bmerge(?:s|r|d)?\b",
    r"\brais(?:es|ed)\b.{0,25}\b(?:million|billion|round|seed|series|funding|\$|€|£)",
    r"\brais(?:es|ed)\s+(?:\$|€|£)", r"\bseed\s+round", r"\bseries\s+[a-e]\b", r"\bfunding\s+round",
    r"\bfiles?\s+for\s+ipo", r"\bipo\b", r"\bintegrat(?:es|ed|ion)",
    r"\blists?\b", r"\blisting\b",
]

# Broader market-event verbs (weaker on their own — a named actor doing a thing).
MARKET_EVENT = STRONG_EVENT + [
    r"\bintroduc(?:es|ed)", r"\bnow\s+(?:live|available)",
    r"\btaps?\b", r"\bselect(?:s|ed)\b", r"\bonboard(?:s|ed)?", r"\badopt(?:s|ed|ion)?",
    r"\bdeploy(?:s|ed)?", r"\badd(?:s|ed)?\s+support", r"\benabl(?:es|ed|ing)",
    r"\bexpand(?:s|ed)\s+(?:to|into)", r"\bexpand(?:s|ed)\s+\w+\s+(?:to|into|across)",
    r"\bsecures?\s+(?:\$|€|£)", r"\bcloses?\s+(?:\$|€|£)",
    r"\binvest(?:s|ed|ment)", r"\bbacks?\b", r"\btakes?\s+(?:a\s+)?stake",
    r"\btakes?\s+over", r"\btook\s+over", r"\bcarr(?:ies|ied)\s+out", r"\breadies\b",
    r"\btokeni[sz]e[sd]?\s+(?:\$|€|£|\d)", r"\bsettl(?:es|ed|ement)", r"\bissu(?:es|ed|ance)",
    r"\bmint(?:s|ed)\b", r"\bhires?\b", r"\bpoach(?:es|ed)?", r"\brebrands?\b",
]

# Concrete regulatory ACTIONS — kept even though they are "regulation",
# because the chosen policy is "keep only concrete actions".
REG_ACTION = [
    r"\bapprov(?:es|ed|al)", r"\bgrants?\s+(?:a\s+)?licen[sc]e", r"\blicen[sc]ed?\b",
    r"\bauthoriz(?:es|ed|ation)", r"\bregisters?\b", r"\bclears?\b", r"\bgreenlights?\b",
    r"\bcharg(?:es|ed)\b", r"\bsues?\b", r"\bsued\b", r"\blawsuit", r"\bindict(?:s|ed|ment)?",
    r"\bfines?\b", r"\bfined\b", r"\bpenalt(?:y|ies)", r"\bsettles?\s+with",
    r"\bsanction(?:s|ed)?", r"\bbans?\b", r"\bbanned\b", r"\bhalts?\b", r"\bseizes?\b",
    r"\brejects?\b", r"\bdenies?\b", r"\brevokes?\b",
]

# Commentary / opinion framing — kill unless a STRONG event is present.
COMMENTARY = [
    r"\bcasts?\b.{0,30}\bas\b",
    r"\brace[sd]?\s+to\b", r"\bracing\s+to\b",
    r"here'?s\s+why", r"\bwhy\s+\w+.{0,40}\bmatters?\b", r"what\s+.{0,40}\bmeans?\b",
    r"\b(?:op-?ed|opinion|analysis|commentary|explainer|perspective|viewpoint|column)\b",
    r"\b(?:argues?|believes?|thinks?|claims?|contends?|insists?|reckons?)\b",
    r"\b(?:warns?|cautions?|frets?|laments?)\b", r"\bsees?\b",
    r"\b(?:weighs?|mulls?|considers?|eyes|exploring|explores?|ponders?)\b",
    r"\breport\s+finds?\b", r"\bsurvey\s+finds?\b",
    r"\blays?\s+groundwork\b", r"\bmoves?\s+forward\b", r"\bcoexist\b",
    r"\b(?:could|might|may|would)\s+(?:be|become|reshape|disrupt|transform|change|mean|spark|generate|coexist)\b",
    r"\bcan\s+\w+\s+but\s+not\b",
    r"\bpoised\s+to\b", r"\bon\s+track\s+to\b", r"\bset\s+to\s+reshape\b",
    r"\bthe\s+(?:future|case|end|dawn|rise|death)\s+of\b",
    r"\bis\s+(?:this|that)\s+the\b",
    r"\bshould\b", r"\bneeds?\s+to\b", r"\btoo\s+much\b", r"\bunsaid\b",
    r"\bquestions?\b", r"\bslams?\b", r"\bcriticis?z?es?\b", r"\bpushes?\s+back\b",
    r"\bcalls?\s+for\b", r"\bcalls?\s+on\b", r"\burges?\b",
]

# Policy / rule-making noise — kill (concrete reg actions are handled earlier).
POLICY_NOISE = [
    r"\brules?\b", r"\bregulation\b", r"\bregulatory\s+framework\b", r"\bframework\b",
    r"\bproposals?\b", r"\bproposes?\b", r"\bconsultation\b", r"\bdraft\s+(?:rules?|bill|law)\b",
    r"\bguidance\b", r"\bguidelines?\b", r"\bissuer\s+limit\b", r"\bcap\s+on\b",
    r"\bpolicy\b", r"\bdilutes?\b", r"\bwaters?\s+down\b", r"\bwatered\s+down\b",
    r"\bdiscuss(?:es|ed|ion)\b", r"\bdebate\b", r"\bhearing\b", r"\btestif(?:y|ies|ied)\b",
    r"\broadmap\b", r"\bstance\b", r"\bsignals?\b",
]

# Political noise — kill unless a hard market deal is also present.
POLITICAL = [
    r"\bsenator\b", r"\bcongress(?:ional)?\b", r"\blawmakers?\b", r"\bparliament\b",
    r"\bsuper\s+pac\b", r"\bpac\b", r"\belection\b", r"\bmidterms?\b",
    r"\bcampaign\b", r"\blobby(?:ing|ist|ists)?\b", r"\bwhite\s+house\b", r"\bpolitical\b",
]

# Low-signal / pure stat / promo / listicle — kill unless a market event verb is present.
LOW_SIGNAL = [
    r"market\s+cap\s+(?:rises?|grows?|tops?|hits?|climbs?|surges?|jumps?|reaches?)",
    r"\baccording\s+to\s+data\b", r"\bdata\s+shows?\b", r"\bnow\s+hosts?\b",
    r"\b\d+(?:\.\d+)?\s*%\b.{0,40}\b(?:of\s+all|share|dominance)\b",
    r"\bprice\s+(?:prediction|target|analysis|surges?|drops?)\b",
    r"\b(?:plunges?|plummets?|soars?|tumbles?|slumps?|rallies)\b",
    r"\btop\s+\d+\b", r"\bbest\s+\d+\b", r"\bthings?\s+to\s+know\b",
    r"\bweekly\s+(?:recap|roundup|digest)\b", r"\broundup\b",
    r"\bmorning\s+minute\b", r"\bdaily\s+brief\b", r"\bsummit\b", r"\bwebinar\b",
]


def _first_match(patterns: list[str], text: str) -> str | None:
    """Return the first matching substring (lowercased) or None."""
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0).strip()
    return None


# Verdict constants
KEEP = "keep"
KILL = "kill"
REVIEW = "review"


def classify(title: str, snippet: str = "") -> dict:
    """
    Classify a story under the strict "market" editorial policy.

    Kill decisions are judged on the TITLE only (snippets are noisy and would
    introduce false kills). Event evidence may come from title OR snippet, so a
    thin headline with a substantive snippet can still be kept.

    Returns a dict:
        {
          "verdict": "keep" | "kill" | "review",
          "axis":    "market_event" | "regulatory_action" | "commentary"
                     | "policy" | "political" | "low_signal",
          "reason":  human-readable one-liner,
          "matched": the trigger phrase (for transparency),
        }
    """
    title_l = (title or "").lower()
    full_l = f"{title or ''}  {snippet or ''}".lower()

    # Kill signals are judged on the TITLE only. The override that lets a concrete
    # event beat soft commentary is ALSO title-based — otherwise a snippet that
    # merely mentions "launched" would rescue a political/commentary headline.
    strong_title = _first_match(STRONG_EVENT, title_l)
    event = _first_match(MARKET_EVENT, full_l)  # snippet may supply event evidence for a thin title
    reg = _first_match(REG_ACTION, title_l)
    commentary = _first_match(COMMENTARY, title_l)
    policy = _first_match(POLICY_NOISE, title_l)
    political = _first_match(POLITICAL, title_l)
    low = _first_match(LOW_SIGNAL, title_l)

    # 1. Political noise — hard kill. Senators / PACs / elections / lobbying are noise
    #    even when the headline says "launch" (e.g. "back launch of a crypto PAC").
    if political:
        return _v(KILL, "political", f"political framing ('{political}')", political)

    # 2. Concrete regulatory ACTION — keep (approval / licence / charge / fine / ban).
    if reg:
        return _v(KEEP, "regulatory_action", f"concrete regulatory action ('{reg}')", reg)

    # 3. Commentary / opinion framing — kill unless a strong concrete event in the title overrides.
    if commentary and not strong_title:
        return _v(KILL, "commentary", f"commentary/opinion framing ('{commentary}')", commentary)

    # 4. Policy / rule-making noise — kill.
    if policy:
        return _v(KILL, "policy", f"policy/rule-making, not a concrete action ('{policy}')", policy)

    # 5. Pure stat / promo / listicle — kill unless a market-event verb is present.
    if low and not event:
        return _v(KILL, "low_signal", f"low-signal stat/promo ('{low}')", low)

    # 6. Any concrete market event — keep.
    if event:
        return _v(KEEP, "market_event", f"concrete market event ('{event}')", event)

    # 7. Nothing decisive — surface for review rather than silently dropping.
    return _v(REVIEW, "low_signal", "no concrete market event or clear noise signal", None)


def _v(verdict: str, axis: str, reason: str, matched: str | None) -> dict:
    return {"verdict": verdict, "axis": axis, "reason": reason, "matched": matched}


# ---------------------------------------------------------------------------
# Optional AI second opinion (strict prompt). Off by default; used by the
# shadow runner only when --ai is passed AND ANTHROPIC_API_KEY is set.
# ---------------------------------------------------------------------------

STRICT_RANKING_PROMPT = """You are the editor of a MARKET-EVENTS fintech wire. You publish only
concrete, market-moving events and you reject regulatory commentary, policy framing, opinion,
political coverage, and statistics-with-narration.

KEEP (concrete market events): product launches and go-lives, partnerships and integrations
between named companies, funding rounds, M&A, institutional adoption, infrastructure milestones,
and CONCRETE regulatory ACTIONS only (an approval granted, a licence issued, a lawsuit filed, a
fine levied, a ban enacted) tied to a named company or market.

REJECT: speeches, op-eds, "X casts Y as Z", "race to define", "here's why", "what X means",
proposals/consultations/rule-making that is not yet an action ("dilutes rules", "issuer limit",
"weighs", "mulls", "considers"), senator/PAC/election/lobbying coverage, and pure statistics or
price commentary ("market cap rises 40%", "now hosts 61% of...").

ARTICLE:
Title: {title}
Snippet: {snippet}

Respond with ONLY valid JSON (no markdown):
{{
  "publish": true or false,
  "axis": "market_event" | "regulatory_action" | "commentary" | "policy" | "political" | "low_signal",
  "reason": "one sentence"
}}"""


def ai_second_opinion(title: str, snippet: str = "") -> dict | None:
    """
    Ask Claude Haiku to adjudicate under the strict market policy.

    Returns {"publish": bool, "axis": str, "reason": str} or None if the API
    key is missing / the call fails (caller should fall back to deterministic).
    """
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import json as _json

        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        prompt = STRICT_RANKING_PROMPT.format(
            title=title or "(no title)", snippet=(snippet or "(no snippet)")[:500]
        )
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(
                l for l in text.split("\n") if not l.strip().startswith("```")
            ).strip()
        result = _json.loads(text)
        return {
            "publish": bool(result.get("publish", False)),
            "axis": str(result.get("axis", "low_signal")),
            "reason": str(result.get("reason", "")),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Self-test: `python -m src.editorial` (or `python src/editorial.py`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # (title, expected_verdict) — the three user complaints + representative keeps/kills.
    CASES = [
        # --- The three the user flagged: must all KILL ---
        ("Fed Governor Casts Tokenization as New Dollar Channel", KILL),
        ("BoE dilutes stablecoin rules with plan for £40bn issuer limit", KILL),
        ("Tokenized RWA market cap rises 40% to top $51 billion as industry races to "
         "define equity tokenization model", KILL),
        # --- Should KEEP: concrete market events ---
        ("JPMorgan launches blockchain deposit token for institutional settlement", KEEP),
        ("Stripe acquires Bridge for $1.1 billion", KEEP),
        ("Circle partners with Visa to enable USDC settlement", KEEP),
        ("Midas raises $50 million Series A, launches liquidity layer for tokenized assets", KEEP),
        ("Mitsubishi adopts JPMorgan blockchain for corporate payments", KEEP),
        ("Aave goes live on X Layer, enabling onchain lending for OKX Wallet users", KEEP),
        ("Swift says blockchain-based shared ledger will go live with real transactions", KEEP),
        ("BNP Paribas Launches Crypto-Linked ETNs for Retail Investors in France", KEEP),
        # --- Should KEEP: concrete regulatory ACTIONS ---
        ("SEC approves first spot ether ETF for listing", KEEP),
        ("SEC sues Binance over unregistered securities", KEEP),
        # --- Should KILL: commentary / policy / political / stat ---
        ("Senator Questions SEC Over Treatment of Trump-Linked Crypto Businesses", KILL),
        ("The SEC's latest crypto guidance still leaves too much unsaid", KILL),
        ("Anchorage Digital, Chainlink back new crypto PAC as election season heats up", KILL),
        ("According to data from Token Terminal, Ethereum now hosts 61.4% of tokenized assets", KILL),
        ("Why stablecoins matter for the future of payments", KILL),
    ]

    width = max(len(t) for t, _ in CASES)
    passed = 0
    for title, expected in CASES:
        r = classify(title)
        ok = r["verdict"] == expected
        passed += ok
        flag = "OK " if ok else "XX "
        print(f"{flag} [{r['verdict']:<6} {r['axis']:<18}] {title[:width]}")
        if not ok:
            print(f"       expected={expected}  reason={r['reason']}")
    print(f"\n{passed}/{len(CASES)} cases passed")
    raise SystemExit(0 if passed == len(CASES) else 1)
