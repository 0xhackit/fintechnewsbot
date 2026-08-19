"""
categorize.py — deterministic 4-way section classifier for the website feed.

Assigns every story exactly one of four sections:

    regulation   — regulators, enforcement, rule-making, licensing, politics
    product      — launches, go-lives, partnerships, integrations, rollouts
    fundraising  — funding rounds, raises, IPOs, strategic investment
    other        — M&A, hires, market stats, commentary, everything else

This is the axis the site's timeline was missing: `ai_category` from the
ranking agent collapsed to "other" for ~90% of entries, so it could not
drive sections.

Pure Python, no network, no API key, deterministic and unit-testable —
same contract as src/editorial.py. Runs free on every item and can be
backfilled over historical feed.json entries.

Decision precedence (first match wins):
    1. FUNDRAISING            — a raise beats everything (a licensed firm
                                closing a Series B is funding news)
    2. HARD regulation        — enforcement / rule-making / politics. Wins
                                even over "launches", because "BoE launches
                                consultation on stablecoin rules" is regulation.
    2.5 MARKET STATISTICS     — market cap / price action / flows -> other
    2.6 PERSONNEL             — hires / appointments / departures -> other
    3. STRONG product verb    — a company shipping a concrete thing. Beats
                                SOFT regulation, so "Coinbase launches in the
                                UK after FCA approval" is a product story.
    4. SOFT regulation        — regulator named, or approval/licence/registration
                                with no concrete product verb ("SEC approves ETF")
    5. WEAK product verb      — adoption, expansion, support
    6. otherwise              — other

Tuning: edit the pattern banks below, then run `python -m src.categorize`
to confirm the labelled cases still pass.
"""

import re

# ---------------------------------------------------------------------------
# Category constants
# ---------------------------------------------------------------------------

REGULATION = "regulation"
PRODUCT = "product"
FUNDRAISING = "fundraising"
OTHER = "other"

CATEGORIES = (REGULATION, PRODUCT, FUNDRAISING, OTHER)

# Display labels used by the frontend / digests.
CATEGORY_LABELS = {
    REGULATION: "Regulation",
    PRODUCT: "Product Updates",
    FUNDRAISING: "Fundraising",
    OTHER: "Others",
}

# Sections that qualify for the high-signal "Latest News" timeline.
HIGH_SIGNAL = (PRODUCT, FUNDRAISING)

# ---------------------------------------------------------------------------
# Pattern banks
# ---------------------------------------------------------------------------

# 1. FUNDRAISING — money going INTO a company.
#    "raise" only counts when tied to money or a round, so "raises concerns"
#    and "raises questions" do not match.
FUNDRAISING_PAT = [
    r"\brais(?:e|es|ed|ing)\b[^.]{0,30}?(?:\$|€|£|¥)\s*\d",
    r"\brais(?:e|es|ed|ing)\b[^.]{0,30}?\b\d[\d.,]*\s*(?:m|k|bn|mn)?\s*"
    r"(?:million|billion|dollars?)\b",
    r"\brais(?:e|es|ed|ing)\b[^.]{0,30}?\b(?:round|funding|capital|seed|series)\b",
    r"\b(?:pre-?)?seed\s+(?:round|funding|financing)\b",
    r"\bseries\s+[a-j]\b",
    r"\bfunding\s+round\b", r"\bfundrais(?:e|es|ed|ing)\b",
    r"\b(?:growth|venture|equity|debt)\s+(?:round|financing)\b",
    r"\bclos(?:es|ed|ing)\b[^.]{0,25}?(?:\$|€|£)\s*\d",
    r"\bsecur(?:es|ed)\b[^.]{0,25}?(?:\$|€|£)\s*\d[^.]{0,25}?"
    r"\b(?:round|funding|investment|financing|capital)\b",
    r"\bsecur(?:es|ed)\b[^.]{0,20}?\b(?:funding|investment|financing|backing)\b",
    r"\bland(?:s|ed)\b[^.]{0,20}?\b(?:funding|investment|backing)\b",
    r"\b(?:oversubscribed|term\s+sheet|cap\s+table)\b",
    r"\bvaluation\s+of\s+(?:\$|€|£)", r"\bat\s+a\s+(?:\$|€|£)[\d.]+\s*"
    r"(?:m|bn|billion|million)\s+valuation\b",
    r"\bfiles?\s+for\s+(?:an?\s+)?ipo\b", r"\bipo\b", r"\bgoes?\s+public\b",
    r"\bdirect\s+listing\b", r"\bspac\b",
    r"\bled\s+by\b[^.]{0,40}?\b(?:capital|ventures|partners|a16z|sequoia|"
    r"paradigm|tiger|accel|index|lightspeed)\b",
    r"\bstrategic\s+investment\b", r"\binvests?\s+(?:\$|€|£)\s*\d",
    r"\binvestment\s+(?:in|round)\b[^.]{0,20}?(?:\$|€|£)\s*\d",
    r"\btoken\s+sale\b", r"\bico\b",
]

# 2a. HARD regulation — enforcement, rule-making, courts, politics.
#     These beat product verbs: a regulator "launching a consultation" is
#     still regulation.
REGULATION_HARD = [
    # rule-making / policy
    r"\bregulat(?:ion|ions|ing|es)\b", r"\bderegulat\w*\b",
    r"\brule-?mak(?:ing|er)\b", r"\brules?\b", r"\bruling\b",
    r"\b(?:draft|new|proposed)\s+(?:bill|law|rules?|legislation)\b",
    r"\blegislation\b", r"\blawmak(?:er|ers|ing)\b", r"\bstatute\b",
    r"\bpolicy\b", r"\bpolicies\b", r"\bframework\b",
    r"\bconsultation\b", r"\bwhite\s+paper\s+on\b",
    r"\bguidance\b", r"\bguidelines?\b", r"\bmandate[sd]?\b",
    r"\bmoratorium\b", r"\bissuer\s+limits?\b",
    r"\bcaps?\s+on\s+(?:issuance|holdings?|stablecoins?|deposits?)\b",
    r"\bcompliance\s+(?:rules?|regime|deadline|requirements?)\b",
    r"\bregulatory\s+sandbox\b", r"\bsandbox\b",
    # named regimes
    r"\bmica\b", r"\bpsd\s?2\b", r"\bpsd\s?3\b", r"\bbasel\s+(?:iii|iv|\d)\b",
    r"\bdodd-?frank\b", r"\bgenius\s+act\b", r"\bclarity\s+act\b",
    r"\btravel\s+rule\b", r"\baml\b", r"\bkyc\b", r"\banti-?money[\s-]launder\w*\b",
    r"\bsanctions?\b", r"\bsanctioned\b", r"\bembargo\b",
    # enforcement / courts
    r"\blawsuits?\b", r"\bsues?\b", r"\bsued\b", r"\bsuing\b",
    r"\bcharg(?:es|ed)\s+(?:\w+\s+){0,3}?with\b", r"\bindict(?:s|ed|ment)?\b",
    r"\bfines?\b", r"\bfined\b", r"\bpenalt(?:y|ies)\b", r"\bfor?feits?\b",
    r"\bsettle(?:s|d|ment)\s+with\b", r"\bconsent\s+order\b",
    r"\bprob(?:e|es|ed|ing)\b", r"\binvestigat(?:es|ed|ion|ions|ing)\b",
    r"\bsubpoena\b", r"\braid(?:s|ed)\b", r"\bseiz(?:es|ed|ure)\b",
    r"\bcrackdown\b", r"\bcracks?\s+down\b", r"\benforcement\b",
    r"\bbans?\b", r"\bbanned\b", r"\bbanning\b", r"\bprohibit(?:s|ed|ion)\b",
    r"\bhalts?\b", r"\bhalted\b", r"\bsuspend(?:s|ed)\b", r"\brevokes?\b",
    r"\bcourt\b", r"\bjudge\b", r"\bjury\b", r"\bappeals?\s+(?:court|ruling)\b",
    r"\bverdict\b", r"\bplea\b", r"\bsentenc(?:e|ed|ing)\b", r"\btestif(?:y|ies|ied)\b",
    r"\bhearings?\b", r"\bsettles?\s+(?:charges|claims|suit)\b",
    # politics
    r"\bsenators?\b", r"\bcongress(?:ional)?\b", r"\bparliament\b", r"\bhouse\s+bill\b",
    r"\bsuper\s+pac\b", r"\bpac\b", r"\belections?\b", r"\bmidterms?\b",
    r"\blobby(?:ing|ist|ists)\b", r"\bwhite\s+house\b", r"\bexecutive\s+order\b",
    r"\bpolitical\b", r"\btariffs?\b", r"\bnominat(?:es|ed|ion)\b",
    r"\bfirst\s+lady\b", r"\bprime\s+minister\b", r"\bpresident\s+(?:trump|biden)\b",
]

# 2b. Regulator / supervisory bodies. On their own these are SOFT — a
#     product verb outranks them.
#     Note: "treasury" is qualified, because "bitcoin treasury company" is a
#     corporate-finance story, not a government one.
REGULATOR_ENTITY = [
    r"\bsec\b", r"\bcftc\b", r"\bocc\b", r"\bfdic\b", r"\bfincen\b", r"\bnydfs\b",
    r"\bfederal\s+reserve\b", r"\bthe\s+fed\b", r"\bfed\s+(?:governor|chair|official)\b",
    r"\bcfpb\b", r"\bdoj\b", r"\bjustice\s+department\b", r"\birs\b", r"\bfhfa\b",
    r"\btreasury\s+department\b", r"\btreasury\s+secretary\b", r"\bhm\s+treasury\b",
    r"\bfca\b", r"\bpra\b", r"\bbank\s+of\s+england\b", r"\bboe\b",
    r"\becb\b", r"\beba\b", r"\besma\b", r"\bbafin\b", r"\bamf\b", r"\bconsob\b",
    r"\beuropean\s+commission\b", r"\beu\s+commission\b",
    r"\bmas\b", r"\bhkma\b", r"\bsfc\b", r"\bjfsa\b", r"\bfsa\b", r"\brbi\b",
    r"\bsebi\b", r"\bpboc\b", r"\basic\b", r"\bapra\b", r"\bbnm\b", r"\bbok\b",
    r"\bcbuae\b", r"\bvara\b", r"\bdfsa\b", r"\bsama\b", r"\bqfc\b",
    r"\bbcb\b", r"\bcnbv\b", r"\bbanxico\b", r"\brba\b", r"\breserve\s+bank\b",
    r"\bcentral\s+bank\b", r"\bregulators?\b", r"\bwatchdog\b", r"\bsupervisor[sy]?\b",
    r"\bauthorit(?:y|ies)\b", r"\bministry\s+of\s+finance\b", r"\bfinance\s+ministry\b",
]

# 2c. SOFT regulation verbs — licensing and approvals. Real regulation, but a
#     concrete product verb in the same headline wins.
REGULATION_SOFT = [
    r"\blicen[sc](?:e|es|ed|ing|ure)\b", r"\bpermit(?:s|ted)\b",
    r"\bapprov(?:es|ed|al|als)\b", r"\bgreen-?lights?\b", r"\bclears?\b",
    r"\bauthoris(?:es|ed|ation)\b", r"\bauthoriz(?:es|ed|ation)\b",
    r"\bregist(?:ers|ered|ration)\b", r"\bcharter(?:s|ed)?\b",
    r"\bexempt(?:s|ed|ion)\b", r"\bwaiver\b", r"\bno-?action\s+letter\b",
    r"\bcompliance\b", r"\bsupervis(?:e|es|ion|ory)\b", r"\boversight\b",
    r"\bregulatory\b", r"\bregulated\b", r"\bregulator[sy]\s+perimeter\b",
]

# 3. STRONG product verbs — a named actor shipping a concrete thing.
#    Per the chosen scope: launches, partnerships, integrations, go-lives.
#    M&A is deliberately NOT here — acquisitions fall to "other".
PRODUCT_STRONG = [
    r"\blaunch(?:es|ed|ing)?\b", r"\brelaunch(?:es|ed)?\b",
    r"\bunveil(?:s|ed|ing)?\b", r"\breveal(?:s|ed)\b[^.]{0,20}?\b(?:product|platform|tool|app)\b",
    r"\brolls?\s+out\b", r"\brolled\s+out\b", r"\broll-?out\b",
    r"\bdebut(?:s|ed|ing)?\b", r"\bintroduc(?:es|ed|ing)\b",
    r"\bgo(?:es)?\s+live\b", r"\bwent\s+live\b", r"\bgoing\s+live\b",
    r"\bnow\s+(?:live|available)\b", r"\bgenerally\s+available\b",
    r"\bships?\b", r"\bshipped\b", r"\breleases?\b[^.]{0,20}?\b(?:version|v\d|app|sdk|api)\b",
    r"\bpartner(?:s|ed|ship|ships)\b", r"\bteams?\s+up\b", r"\bjoins?\s+forces\b",
    r"\bcollaborat(?:es|ed|ion)\b", r"\balliance\b", r"\btie-?up\b",
    r"\bintegrat(?:es|ed|ing|ion)\b", r"\bconnects?\b[^.]{0,25}?\bto\b",
    r"\badds?\s+support\s+for\b", r"\badds?\b[^.]{0,25}?\bsupport\b",
    r"\benabl(?:es|ed|ing)\b", r"\bpowers?\b[^.]{0,25}?\b(?:payments?|settlement|platform)\b",
    r"\bissu(?:es|ed|ing|ance)\b[^.]{0,25}?\b(?:card|cards|token|tokens|stablecoin|bond|bonds)\b",
    r"\btokeni[sz]es\b", r"\btokeni[sz]ing\b", r"\btokeni[sz]ation\s+of\b",
    r"\bto\s+tokeni[sz]e\b", r"\breadies\b", r"\bmainnet\b",
    r"\bofficially\s+(?:live|launched|available|coming)\b", r"\bcoming\s+to\b",
    r"\bcarr(?:ies|ied)\s+out\b",
    r"\bjoins?\b[^.]{0,35}?\b(?:platform|network|initiative|consortium|alliance|as\s+a)\b",
]

# 5. WEAK product verbs — adoption / expansion / selection.
PRODUCT_WEAK = [
    r"\badopt(?:s|ed|ion)\b", r"\bdeploy(?:s|ed|ment)\b",
    r"\btaps?\b", r"\bselect(?:s|ed)\b", r"\bpicks?\b", r"\bchooses?\b",
    r"\bonboard(?:s|ed|ing)\b", r"\bmigrat(?:es|ed|ion)\s+to\b",
    r"\bexpand(?:s|ed|ing)\b[^.]{0,25}?\b(?:to|into|across|beyond)\b",
    r"\bbroadens?\b", r"\bextends?\b[^.]{0,25}?\bto\b",
    r"\bbrings?\b[^.]{0,30}?\bto\b",
    r"\b(?:network|protocol|platform|chain)\s+upgrade\b",
    r"\bupgrades?\s+(?:its|their|the)\b",
    r"\bpilots?\b", r"\bpiloted\b", r"\bproof\s+of\s+concept\b",
    r"\bsettles?\b[^.]{0,25}?\b(?:on-?chain|onchain|transactions?|payments?)\b",
    r"\bmints?\b", r"\bminted\b", r"\bgoes?\s+multi-?chain\b",
]


# 2.5. Pure market statistics / price action — never a product or funding
#      event, even when the words "tokenized" or "launch" appear nearby.
STAT_NOISE = [
    r"\bmarket\s+cap\b", r"\btvl\b", r"\btrading\s+volume\b",
    r"\b(?:rises?|grows?|tops?|hits?|climbs?|surges?|jumps?|reaches?|crosses?)\b"
    r"[^.]{0,20}?(?:\$|€|£)\s*\d",
    r"\b(?:slides?|slips?|falls?|drops?|plunges?|plummets?|tumbles?|slumps?|"
    r"soars?|rallies|rallied)\b",
    r"\bprice\s+(?:prediction|target|analysis|action)\b",
    r"\boutflows?\b", r"\binflows?\b",
    r"\b\d+(?:\.\d+)?\s*%\b[^.]{0,30}?\b(?:of\s+all|share|dominance|supply)\b",
    r"\baccording\s+to\s+data\b", r"\bdata\s+shows?\b",
    r"\bweekly\s+(?:recap|roundup|digest)\b", r"\broundup\b",
    r"\btop\s+\d+\b", r"\bthings?\s+to\s+know\b",
]


# 2.6. Personnel / corporate-people news. Not a product event even when the
#      headline also mentions an upcoming launch ("X hires vet ahead of launch").
PEOPLE_NOISE = [
    r"\bhires?\b", r"\bhired\b", r"\bhiring\b", r"\bpoach(?:es|ed)\b",
    r"\bappoints?\b", r"\bappointed\b", r"\bnames?\b[^.]{0,40}?\b(?:ceo|cfo|cto|coo|"
    r"chief|president|head\s+of|director)\b",
    r"\bsteps?\s+down\b", r"\bresigns?\b", r"\bdeparts?\b", r"\bexits?\b",
    r"\blays?\s+off\b", r"\blayoffs?\b",
]


def _first_match(patterns: list, text: str):
    """Return the first matching substring (lowercased) or None."""
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0).strip()
    return None


def categorize(title: str, snippet: str = "") -> dict:
    """
    Assign a story to one of the four site sections.

    Decisions are made on the TITLE. The snippet is used only as a fallback
    when the title yields nothing decisive, because snippets are noisy and
    routinely mention regulators in passing boilerplate.

    Returns:
        {
          "category": "regulation" | "product" | "fundraising" | "other",
          "label":    display label, e.g. "Product Updates",
          "reason":   human-readable one-liner,
          "matched":  the trigger phrase (for transparency / tuning),
        }
    """
    title_l = (title or "").lower()
    snippet_l = (snippet or "").lower()

    # --- Pass 1: title only ---
    result = _decide(title_l)
    if result is not None:
        return result

    # --- Pass 2: fall back to the snippet for thin headlines ---
    if snippet_l:
        result = _decide(snippet_l[:300], snippet_pass=True)
        if result is not None:
            result["reason"] += " (from snippet)"
            return result

    return _c(OTHER, "no clear regulation, product or funding signal", None)


def _decide(text: str, snippet_pass: bool = False):
    """
    Run the precedence ladder over one blob of text. None = undecided.

    On the snippet pass only unambiguous funding / product / stat evidence is
    accepted: snippets mention regulators in passing boilerplate constantly,
    and trusting them there mislabels product stories as regulation.
    """
    # 1. Fundraising beats everything.
    hit = _first_match(FUNDRAISING_PAT, text)
    if hit:
        return _c(FUNDRAISING, f"funding event ('{hit}')", hit)

    # 2. Hard regulation — enforcement, rule-making, courts, politics.
    if not snippet_pass:
        hit = _first_match(REGULATION_HARD, text)
        if hit:
            return _c(REGULATION, f"regulatory/policy signal ('{hit}')", hit)

    # 2.5. Pure market statistics / price action — bail out to "other" before
    #      an incidental product word can claim it.
    hit = _first_match(STAT_NOISE, text)
    if hit:
        return _c(OTHER, f"market statistics/price action ('{hit}')", hit)

    # 2.6. Personnel news — bail out before a nearby "launch" claims it.
    hit = _first_match(PEOPLE_NOISE, text)
    if hit:
        return _c(OTHER, f"personnel news ('{hit}')", hit)

    # 3. A concrete product verb outranks soft regulation.
    hit = _first_match(PRODUCT_STRONG, text)
    if hit:
        return _c(PRODUCT, f"concrete product event ('{hit}')", hit)

    if snippet_pass:
        return None

    # 4. Soft regulation — regulator named, or approval/licence/registration.
    hit = _first_match(REGULATOR_ENTITY, text)
    if hit:
        return _c(REGULATION, f"regulator involved ('{hit}')", hit)
    hit = _first_match(REGULATION_SOFT, text)
    if hit:
        return _c(REGULATION, f"licensing/approval ('{hit}')", hit)

    # 5. Weaker product signals — adoption, expansion, support.
    hit = _first_match(PRODUCT_WEAK, text)
    if hit:
        return _c(PRODUCT, f"adoption/expansion ('{hit}')", hit)

    return None


def _c(category: str, reason: str, matched):
    return {
        "category": category,
        "label": CATEGORY_LABELS[category],
        "reason": reason,
        "matched": matched,
    }


def is_high_signal(category: str) -> bool:
    """True for the sections that appear in the 'Latest News' timeline."""
    return category in HIGH_SIGNAL


# ---------------------------------------------------------------------------
# Self-test: `python -m src.categorize`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    CASES = [
        # --- FUNDRAISING ---
        ("Valinor Raises $25M Seed Round to Bring Private Credit Onchain", FUNDRAISING),
        ("Midas raises $50 million Series A, launches liquidity layer for tokenized assets", FUNDRAISING),
        ("Midas raises $50M to build instant liquidity layer for tokenized yield", FUNDRAISING),
        ("Fnality closes $95 million funding round led by Goldman Sachs", FUNDRAISING),
        ("Circle files for IPO on the New York Stock Exchange", FUNDRAISING),
        ("Ramp secures $150 million investment at $16bn valuation", FUNDRAISING),

        # --- REGULATION (hard: rules, enforcement, politics) ---
        ("BoE dilutes stablecoin rules with plan for £40bn issuer limit", REGULATION),
        ("Senator Questions SEC Over Treatment of Trump-Linked Crypto Businesses", REGULATION),
        ("The SEC's latest crypto guidance still leaves too much unsaid", REGULATION),
        ("Anchorage Digital, Chainlink back new crypto PAC as election season heats up", REGULATION),
        ("SEC sues Binance over unregistered securities offering", REGULATION),
        ("CFTC fines Ooki DAO $250,000 over unregistered trading", REGULATION),
        ("EU finalises MiCA technical standards for stablecoin issuers", REGULATION),
        ("MAS launches consultation on digital asset custody rules", REGULATION),

        # --- REGULATION (soft: regulator + approval, no product verb) ---
        ("SEC approves first spot ether ETF for listing", REGULATION),
        ("Circle receives MiCA licence from French regulator", REGULATION),
        ("OCC grants national trust charter to Paxos", REGULATION),

        # --- PRODUCT (strong verb wins over soft regulation) ---
        ("Coinbase launches derivatives platform in the UK after FCA approval", PRODUCT),
        ("BNP Paribas Launches Crypto-Linked ETNs for Retail Investors in France", PRODUCT),
        ("Nium Rolls Out Platform for Issuing Stablecoin Cards", PRODUCT),
        ("Nium launches dual-network stablecoin card issuance platform", PRODUCT),
        ("Aave goes live on X Layer, enabling onchain lending for OKX Wallet users", PRODUCT),
        ("Swift says blockchain-based shared ledger will go live with real transactions this year", PRODUCT),
        ("Circle partners with Visa to enable USDC settlement", PRODUCT),
        ("JPMorgan launches blockchain deposit token for institutional settlement", PRODUCT),
        ("Mastercard integrates Paxos stablecoin rails into its settlement network", PRODUCT),

        # --- PRODUCT (weak verb) ---
        ("Mitsubishi adopts JPMorgan blockchain for corporate payments", PRODUCT),
        ("Revolut expands crypto trading into Brazil", PRODUCT),

        # --- OTHER (M&A, stats, hires, commentary) ---
        ("Stripe acquires Bridge for $1.1 billion", OTHER),
        ("Tokenized RWA market cap rises 40% to top $51 billion", OTHER),
        ("Coinbase names former Meta executive as chief technology officer", OTHER),
        ("Bitcoin slides below $90,000 amid ETF outflows", OTHER),

        # --- Regressions found on the live feed ---
        # descriptive "Regulated" adjective must not beat a product verb
        ("ZenithBlox Introduces COBI Architecture for Regulated Enterprise Blockchain Integration", PRODUCT),
        # a product-side fee cap is not an issuer limit
        ("Pump.fun adds one-time cap on creator fee redirects to curb post-launch changes", PRODUCT),
        # "pilot" is weak — a regulator's pilot regime is regulation
        ("ESMA published its report on the EU DLT Pilot Regime, recommending significant changes", REGULATION),
        ("Australia's central bank backs tokenization as pilot finds $16.7B upside", REGULATION),
        ("Australia Lays Groundwork for Tokenized Asset Markets After RBA Project", REGULATION),
        ("First Lady Melania Trump Launches Fostering the Future Together", REGULATION),
        # personnel news outranks a nearby launch
        ("X Hires Coinbase Vet Ahead of X Money Launch", OTHER),
        ("Musk's X hires crypto design lead as X Money nears launch", OTHER),
        # a credit-rating upgrade is not a product upgrade
        ("JTRSY just got upgraded to 'AAAf' by S&P Global Ratings", OTHER),
        # "tokenized Treasury fund" is an asset, not the Treasury Department
        ("Invesco takes over Superstate's $900M tokenized Treasury fund", OTHER),
        # joining a network is a product event
        ("BMO Is First Bank to Join CME's Tokenized Cash Platform on Google Cloud", PRODUCT),
        ("BMO Readies Tokenized Cash Capabilities for Institutional Clients", PRODUCT),
        ("Mastercard carries out agentic payments in Latin America", PRODUCT),
        ("Native USDC is officially coming to Injective", PRODUCT),
    ]

    width = min(88, max(len(t) for t, _ in CASES))
    passed = 0
    failures = []
    for title, expected in CASES:
        r = categorize(title)
        ok = r["category"] == expected
        passed += ok
        flag = "OK " if ok else "XX "
        print(f"{flag} [{r['category']:<11}] {title[:width]}")
        if not ok:
            failures.append((title, expected, r))
            print(f"       expected={expected}  reason={r['reason']}")

    print(f"\n{passed}/{len(CASES)} cases passed")
    raise SystemExit(0 if passed == len(CASES) else 1)
