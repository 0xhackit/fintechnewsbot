/**
 * categories.ts — the four site sections.
 *
 * The authoritative classifier is `src/categorize.py`; it stamps a `category`
 * field onto every feed entry at write time, and `scripts/backfill_categories.py`
 * fills in history.
 *
 * `classifyFallback` below is a deliberately smaller mirror of that logic. It
 * exists only so the site degrades gracefully when a deployed feed.json predates
 * the field — without it, every un-stamped entry would collapse into "Others"
 * and empty the Latest News timeline. Once the feed is fully stamped this code
 * never fires. Tune the Python; treat this as a safety net, not a second policy.
 */

export type Category = "regulation" | "product" | "fundraising" | "other";

export const CATEGORY_ORDER: Category[] = [
  "regulation",
  "product",
  "fundraising",
  "other",
];

export const CATEGORY_LABELS: Record<Category, string> = {
  regulation: "Regulation",
  product: "Product Updates",
  fundraising: "Fundraising",
  other: "Others",
};

/** Sections that qualify for the high-signal "Top" timeline. */
export const HIGH_SIGNAL: Category[] = ["product", "fundraising"];

export function isHighSignal(category: Category): boolean {
  return HIGH_SIGNAL.includes(category);
}

/**
 * Single source of truth for category chip colors (feed + admin). Values match the
 * public feed's original `.post-category-*` CSS so nothing changes visually.
 */
export const CATEGORY_COLORS: Record<Category, { bg: string; fg: string }> = {
  regulation: { bg: "rgba(240,118,29,0.12)", fg: "#b35a13" },
  product: { bg: "rgba(29,155,240,0.12)", fg: "#1573b8" },
  fundraising: { bg: "rgba(0,154,97,0.12)", fg: "#007a4d" },
  other: { bg: "rgba(15,20,25,0.07)", fg: "#536471" },
};

/** Regions (APAC/US/EU/LatAm) — a filter facet, matches src/regions.py labels. */
export const REGIONS = ["APAC", "US", "EU", "LatAm"] as const;
export type Region = (typeof REGIONS)[number];

// ── Fallback classifier (mirror of src/categorize.py, abridged) ──

const FUNDRAISING_RE = [
  /\brais(?:e|es|ed|ing)\b[^.]{0,30}?[$€£]\s*\d/,
  /\brais(?:e|es|ed|ing)\b[^.]{0,30}?\b(?:round|funding|capital|seed|series)\b/,
  /\bseries\s+[a-j]\b/,
  /\b(?:pre-?)?seed\s+(?:round|funding|financing)\b/,
  /\bfunding\s+round\b/,
  /\bfundrais(?:e|es|ed|ing)\b/,
  /\bclos(?:es|ed|ing)\b[^.]{0,25}?[$€£]\s*\d/,
  /\bsecur(?:es|ed)\b[^.]{0,20}?\b(?:funding|investment|financing|backing)\b/,
  /\bfiles?\s+for\s+(?:an?\s+)?ipo\b/,
  /\bipo\b/,
  /\bgoes?\s+public\b/,
  /\bstrategic\s+investment\b/,
  /\bvaluation\s+of\s+[$€£]/,
];

const REGULATION_HARD_RE = [
  /\bregulat(?:ion|ions|ing|es)\b/,
  /\brules?\b/,
  /\bruling\b/,
  /\blegislation\b/,
  /\blawmak(?:er|ers|ing)\b/,
  /\bpolicy\b/,
  /\bframework\b/,
  /\bconsultation\b/,
  /\bguidance\b/,
  /\bguidelines?\b/,
  /\bmica\b/,
  /\bclarity\s+act\b/,
  /\bgenius\s+act\b/,
  /\btravel\s+rule\b/,
  /\bsanctions?\b/,
  /\blawsuits?\b/,
  /\bsues?\b/,
  /\bsued\b/,
  /\bfines?\b/,
  /\bfined\b/,
  /\bpenalt(?:y|ies)\b/,
  /\bprob(?:e|es|ing)\b/,
  /\binvestigat(?:es|ed|ion|ions|ing)\b/,
  /\bcrackdown\b/,
  /\bbans?\b/,
  /\bbanned\b/,
  /\bcourt\b/,
  /\bhearings?\b/,
  /\bsenators?\b/,
  /\bcongress(?:ional)?\b/,
  /\bparliament\b/,
  /\bpac\b/,
  /\belections?\b/,
  /\bmidterms?\b/,
  /\blobby(?:ing|ist|ists)\b/,
  /\bwhite\s+house\b/,
  /\bexecutive\s+order\b/,
  /\bfirst\s+lady\b/,
];

const REGULATOR_RE = [
  /\bsec\b/,
  /\bcftc\b/,
  /\bocc\b/,
  /\bfdic\b/,
  /\bfincen\b/,
  /\bnydfs\b/,
  /\bcfpb\b/,
  /\bdoj\b/,
  /\bfederal\s+reserve\b/,
  /\bfca\b/,
  /\bpra\b/,
  /\bbank\s+of\s+england\b/,
  /\bboe\b/,
  /\becb\b/,
  /\beba\b/,
  /\besma\b/,
  /\bbafin\b/,
  /\bmas\b/,
  /\bhkma\b/,
  /\bjfsa\b/,
  /\brbi\b/,
  /\bpboc\b/,
  /\basic\b/,
  /\brba\b/,
  /\bcentral\s+bank\b/,
  /\breserve\s+bank\b/,
  /\bregulators?\b/,
  /\bwatchdog\b/,
  /\btreasury\s+department\b/,
  /\bmonetary\s+authority\b/,
  /\bauthorit(?:y|ies)\b/,
];

const REGULATION_SOFT_RE = [
  /\blicen[sc](?:e|es|ed|ing)\b/,
  /\bapprov(?:es|ed|al|als)\b/,
  /\bauthoris(?:es|ed|ation)\b/,
  /\bauthoriz(?:es|ed|ation)\b/,
  /\bregist(?:ers|ered|ration)\b/,
  /\bchartered?\b/,
  /\bcompliance\b/,
  /\bregulatory\b/,
  /\bregulated\b/,
  /\boversight\b/,
];

const STAT_NOISE_RE = [
  /\bmarket\s+cap\b/,
  /\btvl\b/,
  /\btrading\s+volume\b/,
  /\b(?:slides?|slips?|falls?|drops?|plunges?|plummets?|tumbles?|slumps?|soars?|rallies)\b/,
  /\bprice\s+(?:prediction|target|analysis|action)\b/,
  /\b(?:out|in)flows?\b/,
  /\baccording\s+to\s+data\b/,
  /\bdata\s+shows?\b/,
  /\broundup\b/,
  /\bthings?\s+to\s+know\b/,
];

const PEOPLE_NOISE_RE = [
  /\bhires?\b/,
  /\bhired\b/,
  /\bhiring\b/,
  /\bappoints?\b/,
  /\bappointed\b/,
  /\bsteps?\s+down\b/,
  /\bresigns?\b/,
  /\blayoffs?\b/,
];

const PRODUCT_STRONG_RE = [
  /\blaunch(?:es|ed|ing)?\b/,
  /\bunveil(?:s|ed|ing)?\b/,
  /\brolls?\s+out\b/,
  /\brolled\s+out\b/,
  /\bdebut(?:s|ed|ing)?\b/,
  /\bintroduc(?:es|ed|ing)\b/,
  /\bgo(?:es)?\s+live\b/,
  /\bwent\s+live\b/,
  /\bnow\s+(?:live|available)\b/,
  /\bpartner(?:s|ed|ship|ships)\b/,
  /\bteams?\s+up\b/,
  /\bjoins?\s+forces\b/,
  /\bcollaborat(?:es|ed|ion)\b/,
  /\bintegrat(?:es|ed|ing|ion)\b/,
  /\badds?\s+support\s+for\b/,
  /\benabl(?:es|ed|ing)\b/,
  /\bmainnet\b/,
  /\breadies\b/,
  /\bto\s+tokeni[sz]e\b/,
  /\bcoming\s+to\b/,
  /\bcarr(?:ies|ied)\s+out\b/,
  /\bjoins?\b[^.]{0,35}?\b(?:platform|network|initiative|consortium|alliance|as\s+a)\b/,
];

const PRODUCT_WEAK_RE = [
  /\badopt(?:s|ed|ion)\b/,
  /\bdeploy(?:s|ed|ment)\b/,
  /\btaps?\b/,
  /\bselect(?:s|ed)\b/,
  /\bonboard(?:s|ed|ing)\b/,
  /\bexpand(?:s|ed|ing)\b[^.]{0,25}?\b(?:to|into|across)\b/,
  /\bbroadens?\b/,
  /\bpilots?\b/,
  /\bmints?\b/,
];

const any = (res: RegExp[], text: string) => res.some((re) => re.test(text));

/** Abridged mirror of src/categorize.py's precedence ladder. */
export function classifyFallback(title: string, snippet: string = ""): Category {
  const t = (title || "").toLowerCase();
  if (any(FUNDRAISING_RE, t)) return "fundraising";
  if (any(REGULATION_HARD_RE, t)) return "regulation";
  if (any(STAT_NOISE_RE, t)) return "other";
  if (any(PEOPLE_NOISE_RE, t)) return "other";
  if (any(PRODUCT_STRONG_RE, t)) return "product";
  if (any(REGULATOR_RE, t)) return "regulation";
  if (any(REGULATION_SOFT_RE, t)) return "regulation";
  if (any(PRODUCT_WEAK_RE, t)) return "product";

  // Thin headline — retry on the snippet, but only for unambiguous evidence.
  const s = (snippet || "").toLowerCase().slice(0, 300);
  if (s) {
    if (any(FUNDRAISING_RE, s)) return "fundraising";
    if (any(PRODUCT_STRONG_RE, s)) return "product";
  }
  return "other";
}

/** Read the stamped category, falling back to the local classifier. */
export function resolveCategory(entry: {
  category?: string;
  title?: string;
  snippet?: string;
}): Category {
  const stamped = (entry.category || "").toLowerCase();
  if (CATEGORY_ORDER.includes(stamped as Category)) return stamped as Category;
  return classifyFallback(entry.title || "", entry.snippet || "");
}
