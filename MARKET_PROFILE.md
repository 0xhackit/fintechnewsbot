# v2 review pipeline

A **separate, deterministic, $0-LLM** pipeline for evaluating a stricter, tagged feed
**without touching the live bot**. It fetches Google News RSS only (no Telegram), applies a
market-events editorial gate, tags each story by **region** and **site section**, gates on
**source tier**, and writes a kept / review / killed report shown in the **admin panel**
(`/dashboard` → "Review queue"). Nothing is posted; production posting is untouched.

## Modules

| File | Role |
|---|---|
| `src/editorial.py` | Market-event vs commentary/policy/political/low-signal gate. `classify(title, snippet)`. Deterministic, self-tested. |
| `src/regions.py` | APAC / US / EU / LatAm gazetteer (multi-label). `classify_region(title, snippet)`. Self-tested. |
| `src/categorize.py` | The site's 4 sections (regulation / product / fundraising / other). `categorize(title, snippet)`. Single categorizer, shared with the public feed. Self-tested (46/46). |
| `src/enrich_fulltext.py` | Jina Reader full-text (vendored; free, cached, fail-soft). Enriches survivors only. |
| `sources.json` | Tier A/B/C trust map over `config.json` feeds (read-only; config untouched). |
| `scripts/standalone_pipeline.py` | The pipeline. Reuses existing fetch/score/dedupe leaf functions. Writes `out/market/standalone/`. |
| `frontend/components/ReviewQueue.tsx` | Admin triage UI (kept/review/killed + region + section filters), served by `app/api/market/route.ts`. |

## Run it

```bash
cd mvp/fintech-news-mvp
python scripts/standalone_pipeline.py                 # live RSS → editorial → region/section → tier gate
python scripts/standalone_pipeline.py --input items   # reuse out/items_last24h.json (offline)
python scripts/standalone_pipeline.py --no-fulltext   # skip Jina (fastest offline)
```

Sanity-check the deterministic engines:

```bash
python -m src.editorial     # editorial gate self-test
python -m src.regions       # region gazetteer self-test
python -m src.categorize    # 4-section categorizer self-test
```

## Pipeline flow

fetch RSS → normalize → match → window → score → cluster → **editorial gate** (drop commentary/
policy/political/low-signal) → **full-text enrich survivors** (Jina) → **region + section tag** →
**balanced signal gate** (Tier-A/B publisher OR ≥2-source consensus OR material $) → dedup → write.

Region is a **filter, not a gate** (global crypto news often has no region). Everything runs
deterministically at $0 LLM cost.

## View it

Run the frontend (`cd frontend && npm run dev`), open **`/dashboard`**, enter the dashboard
password → **Review queue** tab. Filter by region and section; switch kept / review / killed; hit
↻ after re-running the pipeline. The public `/` feed shows the curated, categorized reader feed.

## Tuning

Pattern banks live at the top of `src/editorial.py`, `src/regions.py`, and `src/categorize.py`.
Edit a bank, run that module's self-test, then re-run `standalone_pipeline.py` to see the effect.
