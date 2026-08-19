# v2 editorial pipeline

A **deterministic, $0-LLM** gate that decides what the bot publishes. It fetches
Google News RSS (Telegram ignored as a data source), applies a market-events
editorial policy, tags each story by **region** and **site section**, gates on
**source tier**, and routes every story to one of three buckets:

- **KEEP** → posts **automatically**: Telegram + the website feed (the feed *is*
  the site). A high-quality subset also posts to **X**. No human in the loop.
- **REVIEW** → held in the **admin Review queue** (`/dashboard`). You decide:
  **Publish** (→ Telegram + feed) or **Kill** (never resurfaces).
- **KILLED** → dropped (kept in `killed.json` only for auditability).

This replaces the old Claude Haiku ranking agent with deterministic pattern
banks — same routing, $0 per article, fully explainable.

## Modules

| File | Role |
|---|---|
| `src/editorial.py` | Market-event vs commentary/policy/political/low-signal gate. `classify(title, snippet)`. Deterministic, self-tested (18/18). |
| `src/regions.py` | APAC / US / EU / LatAm gazetteer (multi-label). `classify_region(title, snippet)`. Self-tested (9/9). |
| `src/categorize.py` | The site's 4 sections (regulation / product / fundraising / other). `categorize(title, snippet)`. Shared with the public feed. Self-tested (46/46). |
| `src/enrich_fulltext.py` | Jina Reader full-text (vendored; free, cached, fail-soft). Enriches survivors only. |
| `src/pipeline_v2.py` | **The shared brain.** `evaluate_item()` → `kept`/`review`/`killed`; `build_draft()` → posting draft; `qualifies_for_x()` → the X quality gate. Used by *both* callers below so the preview you tune is exactly what production posts. |
| `sources.json` | Tier A/B/C trust map over `config.json` feeds (read-only). |
| `scripts/prepare_alerts_v2.py` | **Production.** Reads `out/items_last24h.json`, runs the gate with real dedup state, writes `out/alerts_drafts.json` (KEEP) + the admin JSONs. Replaces `scripts/run_alerts.py` in the workflow. |
| `scripts/standalone_pipeline.py` | **Preview / tuning.** Same brain, isolated dedup DB, **posts nowhere**. For experimenting with the pattern banks against live RSS without side effects. |
| `frontend/components/ReviewQueue.tsx` | Admin triage UI (kept/review/killed + region + section filters + Publish/Kill on Review), served by `app/api/market/route.ts`. |
| `frontend/app/api/review-action/route.ts` | Publish / Kill actions for the Review bucket. |

## How posting is wired (production)

```
run.py (fetch + score)  →  out/items_last24h.json
        │
        ▼
scripts/prepare_alerts_v2.py   (deterministic, $0 LLM)
   editorial gate → full-text enrich → region/section → source-tier gate → dedup
        ├─ KEEP    → out/alerts_drafts.json   (post_to_x set on the quality subset)
        ├─ REVIEW  → out/market/standalone/review.json   (admin decides)
        └─ KILLED  → dropped
        │
        ▼
post_alerts_now.py   → Telegram + writes out/feed.json  (= the website feed)
scripts/publish_x.py → X, only drafts where post_to_x == true
```

The posting scripts (`post_alerts_now.py`, `scripts/publish_x.py`) and the feed
(`out/feed.json`) are **unchanged** — `prepare_alerts_v2.py` simply produces the
same `alerts_drafts.json` they already consume. Telegram and the website feed are
the same set (posting to Telegram writes the feed entry).

### "High quality → X" gate (`pipeline_v2.qualifies_for_x`, tunable)

KEEP is already the high-signal set. X is the public megaphone, so it takes only
the **strongest subset** of KEEP — a story qualifies for X if **any** holds:

- source is **Tier A** (FT / WSJ / TechCrunch / Stripe / primary), **or**
- **financial_bonus ≥ 40** (materially large, ≈ $100M+), **or**
- **≥ 3 independent sources** on the same story, **or**
- automated **score ≥ 70**.

Everything else in KEEP goes to Telegram + feed only. X still respects the
existing 40/day cap in `publish_x.py`.

## Gate rules (kept vs review)

Publish to **KEEP** when editorial says KEEP **and** the story is high-signal:
Tier-A/B publisher **OR** ≥2-source consensus **OR** financial_bonus ≥ 40.
Otherwise → **REVIEW**. Region is a *filter, not a gate* (global crypto news
often has no region). Below the score floor (35) or editorial KILL → dropped.

## Run it

```bash
cd mvp/fintech-news-mvp
python run.py                                   # refresh out/items_last24h.json
python scripts/prepare_alerts_v2.py             # production: write drafts + admin JSONs + dedup state
python scripts/prepare_alerts_v2.py --dry-run   # compute + preview; touch NO state (safe to inspect)
python scripts/standalone_pipeline.py           # preview/tuning: isolated, posts nowhere
```

Sanity-check the deterministic engines:

```bash
python -m src.editorial     # 18/18
python -m src.regions       # 9/9
python -m src.categorize    # 46/46
```

## View it

Run the frontend (`cd frontend && npm run dev`), open **`/dashboard`**, enter the
dashboard password → **Review queue**. Filter by region and section; switch
kept / review / killed; on **Review**, Publish or Kill each item. The public `/`
feed shows what actually posted.

## TreeOfAlpha consensus source (`config.json` → `tree.enabled`)

TreeOfAlpha aggregates X/Twitter + blogs + wires into one structured, real-time,
server-friendly stream (no cookies, no ban risk, runs in CI). It's noisy, so it rides
the **same v2 gate** as RSS. The payoff is **cross-source consensus**:

- `src/fetch_tree.py` fetches Tree (public REST — no key needed), normalizes, applies
  the same relevance + scoring as RSS, then `merge_consensus()` corroborates: a Tree
  item matching an RSS story **bumps that story's consensus (+1 source)** and is
  absorbed; unmatched Tree items pass through as single-source candidates.
- In `prepare_alerts_v2.py` (behind `tree.enabled`), the merged pool runs the gate.
  A story both RSS **and** Tree report reaches `consensus ≥ 2` → **auto-keep** (as long
  as editorial says KEEP — editorial KILL/REVIEW still has veto over consensus).
- Every record carries `origin` = `rss` | `tree` | `rss+tree`; the admin Review queue
  shows a **Tree** or **✓ consensus** badge accordingly.
- Tree items default to **Tier C** (`src/fetch_tree.py::TREE_TRUSTED_TIER_B` promotes a
  few reliable aggregator sources to B). The API key (`TREE_API_KEY`) is only needed for
  the real-time WebSocket upgrade — the batch REST path works without it.

Preview it in isolation (posts nowhere) before enabling:

```bash
python scripts/fetch_tree_local.py --limit 300           # Tree-only preview → out/market/tree/
python scripts/prepare_alerts_v2.py --dry-run --tree     # full RSS+Tree merge, touches no state
```

## Tuning

Pattern banks live at the top of `src/editorial.py`, `src/regions.py`, and
`src/categorize.py`; the KEEP and X thresholds live at the top of
`src/pipeline_v2.py`; Tree tiers/trusted-sources at the top of `src/fetch_tree.py`.
Edit, run that module's self-test, then re-run `standalone_pipeline.py` (RSS preview) or
`fetch_tree_local.py` (Tree preview) to see the effect before it reaches production.
