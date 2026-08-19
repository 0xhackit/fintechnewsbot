# Market profile (shadow feed)

A **separate, read-only** editorial profile for evaluating a stricter "market events only"
policy **without touching the live bot**. It keeps concrete market events (launches, deals,
funding, integrations, M&A, go-lives) and concrete regulatory **actions** (approval granted,
licence issued, lawsuit filed, fine levied, ban enacted). It kills regulatory **commentary**,
policy/rule-making framing, political coverage, and low-signal stat/promo pieces.

Motivation: the broad pipeline actively *promotes* regulatory/policy/commentary content
(see "Why the live bot surfaces this" below), so these need a dedicated axis to filter on.

## Files

| File | Role |
|---|---|
| `src/editorial.py` | The policy engine: `classify(title, snippet) -> {verdict, axis, reason, matched}`. Deterministic, no network. Optional `ai_second_opinion()` (Claude Haiku). |
| `scripts/shadow_market.py` | Read-only runner. Reads existing pipeline output, writes a report to `out/market/<source>/`. Posts nothing, writes no `state/`. |
| `out/market/<source>/` | Per source (`feed`, `items`): `kept.json`, `killed.json`, `review.json`, `meta.json`, `digest.md` (regenerated each run). |
| `frontend/app/market/` + `components/MarketReport.tsx` | Preview UI at `/market` — source toggle, KEEP/KILL/REVIEW tabs, axis badges, trigger phrases, "generated …" timestamp. |

Nothing here imports into or modifies `run_alerts.py`, `post_alerts_now.py`, scoring, or state.
The live Telegram/X feed is unaffected until you explicitly promote this (see below).

## Run it

```bash
# Generate BOTH sources (published feed + current candidates) — default
python scripts/shadow_market.py

# Just one source
python scripts/shadow_market.py --source feed     # last N already-PUBLISHED items (best signal)
python scripts/shadow_market.py --source items    # current live candidates

# Add a Claude Haiku second opinion (needs ANTHROPIC_API_KEY); flags disagreements
python scripts/shadow_market.py --ai

# Sanity-check the policy on labelled examples
python -m src.editorial
```

**Preview UI:** run the frontend (`cd frontend && npm run dev`) and open **`/market`**. Toggle
between *Published feed* and *Current candidates*, browse the KEEP / KILL / REVIEW tabs, and hit
↻ after re-running the script. Or read `out/market/<source>/digest.md` directly.

## How to read it

- **KEEP** — concrete market event or concrete regulatory action. This is the market feed.
- **KILL** — commentary / policy / political / low-signal. This is the noise removed.
  The digest groups these by axis and shows the trigger phrase for every decision.
- **REVIEW** — genuinely ambiguous (no clear event verb, no clear noise signal). Eyeball these.
  In production these route to the AI second opinion, or default to KILL under strict mode.

## Why the live bot surfaces this today

1. `src/improved_scoring.py` has two overrides that floor regulator/central-bank stories at 50:
   - `if regulatory_bonus >= 40: score = max(score, 50)`  (regulator + "rules/approves/…")
   - `if has_central_bank and has_crypto: score = max(score, 50)`
2. `src/ranking_agent.py` lists "significant regulatory actions" as **high** tier and has no
   market-vs-commentary axis.

## Promotion path (when the shadow feed looks right)

Do these **only after** the shadow report consistently matches your taste. Each is small and reversible:

1. **Gate the scoring overrides** in `src/improved_scoring.py`: drop (or make conditional on a
   concrete `REG_ACTION`) the `regulatory_bonus >= 40` and `central_bank + crypto` floors so
   policy/commentary no longer gets a free pass to 50.
2. **Wire the editorial axis into `run_alerts.py`**: after the score gate, call
   `editorial.classify(title, snippet)`; drop `kill`, send `review` to `editorial.ai_second_opinion()`
   (or drop under strict mode), and let `keep` proceed to the ranking agent.
3. **Swap the ranking prompt**: replace `RANKING_PROMPT` in `src/ranking_agent.py` with the strict
   market wording (mirrors `editorial.STRICT_RANKING_PROMPT`) so "high"/"medium" require a concrete,
   named market event.
4. Optionally guard all of the above behind an `EDITORIAL_PROFILE=market` env var so you can flip
   between `broad` (today) and `market` (strict) without a code change.

## Tuning

All policy lives in the pattern banks at the top of `src/editorial.py`
(`STRONG_EVENT`, `MARKET_EVENT`, `REG_ACTION`, `COMMENTARY`, `POLICY_NOISE`, `POLITICAL`,
`LOW_SIGNAL`). Add a phrase, then run `python -m src.editorial` to confirm the labelled cases
still pass, and `python scripts/shadow_market.py --source feed` to see the effect on real data.
