# v2 architecture — regions, more sources, higher signal, controlled cost

Design of record. **Nothing here is deployed yet.** This builds on what already exists:
the deterministic editorial engine (`src/editorial.py`) and the standalone, Telegram-free,
LLM-free pipeline (`scripts/standalone_pipeline.py`).

## Goals

1. **Region labels** — tag every story `APAC | US | EU | LatAm` (multi-label + `Global`).
2. **More sources, higher signal** — expand ingestion but raise the publish bar.
3. **Controlled LLM cost** — do not send the raw fire hose to a model.

## Decisions (locked)

- **Region delivery:** one feed, region as **metadata + filter chips** (APAC/US/EU/LatAm) in the admin review queue (`/dashboard`).
  Multi-region items appear under each matching chip. Per-region channels deferred until labeling is proven.
- **Signal bar:** **balanced gate** — publish if `KEEP` AND region-resolved AND (Tier-A source OR ≥2-outlet consensus OR material $ size). See §3.

## The cost principle: LLM as a scalpel, not a fire hose

The one rule everything follows from: **never LLM-classify raw ingest.** Cheap deterministic
filters carry the volume; the model only touches the small set that survives, where its
judgment actually adds value. Concretely, a five-stage cascade (see the diagram):

| Stage | What runs | Volume/day | Cost |
|---|---|---|---|
| 0 Ingest | fetch → normalize → hard-dedupe | ~1500 → 800 | $0 |
| 1 Classify | keyword match → `editorial.classify` → **region tag** | 800 → ~120 | $0 (CPU) |
| 2 Cluster | semantic dedup + consensus | ~120 → ~70 | ≈$0 |
| 3 Tie-break | **Haiku 4.5** on the ~8% REVIEW bucket + region-unknown | ~20 | ≈$6/mo |
| 4 Enrich | **Sonnet 4.6** "so what" line + entity/deal extraction on publishables | ~30 | ≈$3/mo |

Deterministic stages absorb 90%+ of volume for free. The LLM sees <15% of items. **Adding
3–5× more sources multiplies stage 0–2 (free) work, not the LLM bill.** Contrast: LLM-classifying
everything would be ~$50–60/mo *today* and scales linearly with every source you add.

## 1. Region labeling — `src/regions.py` (deterministic-first)

Same pattern as `editorial.py`: a gazetteer of region signals, matched on the title (snippet as
tiebreak). ~85% of fintech stories name a regulator, scheme, currency, or company that maps
cleanly to a region.

```
REGION_SIGNALS = {
  "US":    {regulators: SEC, Fed, OCC, FDIC, CFTC, FinCEN, NYDFS;  schemes: FedNow, ACH;
            firms: Circle, Coinbase, JPMorgan, Stripe, Plaid, Visa/MC(HQ); ccy: USD; geo: "United States", NY, SF}
  "EU":    {regulators: ECB, EBA, ESMA, BaFin, FCA, PRA, BoE;  frameworks: MiCA, PSD2, SEPA;
            firms: Revolut, Wise, Adyen, Klarna, N26, Monzo; ccy: EUR, GBP; geo: London, Frankfurt, Paris, EU}
  "APAC":  {regulators: MAS, HKMA, JFSA, RBI, PBoC, ASIC, BNM, BoK;  schemes: UPI, PayNow, FPS, PromptPay;
            firms: DBS, Ant/Alipay, Grab, Sea, Paytm; ccy: SGD, HKD, JPY, INR, CNY; geo: Singapore, HK, Tokyo, India, China}
  "LatAm": {regulators: BCB(Brazil), CNBV(Mexico), CMF(Chile);  schemes: Pix, SPEI, CoDi;
            firms: Nubank, MercadoPago, dLocal, Bitso, Ualá; ccy: BRL, MXN, ARS; geo: Brazil, Mexico, Argentina}
}
```

`classify_region(title, snippet) -> {regions: [...], primary: str, source: "deterministic"|"ai"}`

- Multi-label (a JPMorgan-in-Singapore story is `US` + `APAC`); `primary` = strongest signal.
- **Regulators / currencies / schemes are strong signals** (title-weighted); firm HQ is weaker.
- 0 hits or genuine conflict → `regions: []`, routes to **Stage 3 Haiku** for a one-shot region call.
- **Note: UK is folded into EU** for now (regulatory-adjacent). Split it out later if you want `UK` separate — one line in the gazetteer.

Runs in Stage 1, free, on every candidate. Testable the same way `editorial.py` is (labelled cases + self-test).

## 2. Source registry — `sources.yaml` (tiered)

Replace the flat feed list with a registry carrying tier + type + default region. Tier drives the
signal score and the publish bar.

| Tier | What | Examples | Signal weight |
|---|---|---|---|
| **A — primary** | Regulator/central-bank press, company newsrooms, filings | SEC press RSS, ESMA, MAS, FCA, HKMA; Stripe/Circle/PayPal newsroom; SEC EDGAR 8-K | high |
| **B — quality trade** | Vetted fintech/crypto press | The Block, DL News, Blockworks, Finextra, PYMNTS, Ledger Insights, The Banker | medium |
| **C — aggregator** | Broad, noisy | Google News RSS queries (today's default) | low (needs corroboration) |

Each entry: `{name, url, type: rss|api, tier, default_regions?}`. Tier-A primary sources are the
biggest single lever on signal — you break from the source instead of from secondary coverage.

## 3. Higher-signal publish gate

Signal is not one number — it's a **gate** combining what we already compute:

```
publish if:
   editorial.verdict == KEEP                        # concrete market event or reg action
   AND region resolved (any of APAC/US/EU/LatAm)    # drop un-geo-able noise
   AND ( source.tier == A                            # primary source, trust it alone
         OR consensus_count >= 2                      # ≥2 independent outlets = corroborated
         OR financial_bonus >= 40 )                   # material $ size
```

Everything else → the frontend "review" view, not the live feed. This is stricter than today's
flat `score >= 35`, and it's the knob for "higher signal": tighten the AND-clause to publish less,
loosen to publish more. All inputs already exist except `consensus_count` (from Stage 2 clustering)
and `source.tier` (from the registry).

## 4. Model selection (per use case)

| Job | Model | Why | Price (in/out per MTok) |
|---|---|---|---|
| Classify / rank / region — bulk | **deterministic** (`editorial.py` + `regions.py`) | 90%+ of volume, $0, predictable | — |
| Tie-break the REVIEW + region-unknown tail | **Haiku 4.5** | cheap, fast, only ~10% of volume | $1 / $5 |
| "So what" line + entity/deal extraction on publishables | **Sonnet 4.6** | better judgment, low volume | $3 / $15 |
| Weekly digest synthesis / deep analysis (rare) | **Opus 4.8** | high-value, infrequent | $5 / $25 |

Do **not** use Fable 5 here — it's for long-horizon agentic work, ~2× Opus price, overkill for classification.

**Three cost levers, in order of impact:**
1. **Deterministic-first** (this whole design) — biggest lever by far.
2. **Batches API** — Stages 3–4 aren't real-time; batching is **50% off** all tokens.
3. **Prompt caching** — the classification instructions + few-shot examples are a fixed prefix;
   caching them is ~90% off the cached portion (cache-read ≈ 0.1× input). Put the volatile article
   text after the breakpoint.

## Cost model (rough, at 3–5× current sources)

- LLM touches ~50 items/day (20 tie-break + 30 enrich).
- Tie-break (Haiku, batched): 20 × ~550 tok × blended → **≈$0.20/day**.
- Enrich (Sonnet, batched): 30 × ~700 tok → **≈$0.10/day**.
- **Total ≈$5–15/month**, and roughly flat as sources grow (new sources add free stage-0–2 work).
- Semantic dedup embeddings (Stage 2, optional) use a third-party embedding model (Anthropic has no
  embeddings API — Voyage `voyage-3-lite` is the usual pick, ~pennies/day). Or skip it and keep the
  existing Jaccard/entity dedup — that path stays $0.

## 5. Audio/video ingestion (podcasts + YouTube) — a new modality

Long-form audio is a **different kind of input** and must be treated as one, or it re-pollutes the
signal. The cascade principle applies harder here (see the audio/video diagram):

- **A0 Detect on launch (free).** Podcasts *are* RSS — poll each show's feed; new `<item>` = new
  episode within minutes. YouTube: subscribe via **WebSub / PubSubHubbub** (`youtube.com/feeds/videos.xml`)
  for a near-instant push the moment a video publishes; fall back to channel-RSS polling.
- **A1 Get transcript (free-first).** Prefer an **existing** transcript before paying to make one:
  the podcast RSS spec has a `<podcast:transcript>` tag; YouTube ships auto-captions. Only when none
  exists do you run speech-to-text. **Transcription is not an Anthropic capability** — Claude can't
  ingest audio. Use Whisper (self-hosted, free-but-compute) or a hosted STT API (Deepgram/AssemblyAI/
  Whisper API ≈ **$0.006/min** → ~$0.36 for a 60-min episode). Free-first keeps most episodes at $0.
- **A2 Segment filter (free, deterministic).** Chunk the transcript by timestamp/speaker; keep only
  segments that mention a fintech entity, a `$` amount, or a deal/product verb. This drops ~90% of
  runtime (intros, ads, tangents) **before any LLM touches it**. This is the cost control.
- **A3 Extract (Haiku, survivors only).** Run Haiku over the *candidate segments*, not the whole
  transcript → `{claim, speaker, timestamp, type: fact|quote|disclosure, entities, confidence}`.
  Reuse the market-vs-commentary axis from `editorial.py` to separate a concrete disclosure from an
  opinion.
- **A4 Verify + route (gate).** Concrete disclosures ("we're launching X", "we processed $Y") →
  keep, with **full provenance** (show, episode, timestamp, speaker) + confidence. Cross-check
  high-value claims against text sources; a genuine scoop → **flag for human review** before
  publishing. Opinion → drop.

### The framing correction: podcasts are NOT "Breaking news"

Podcasts and YouTube are recorded hours-to-days before they publish, and they are almost entirely
**commentary** — which is exactly the noise class this project spent three iterations removing. A
podcast dropping doesn't mean news broke; it means an opinion got published. So:

- **Breaking = the text / primary-source lane** (fast, factual, market events). Audio can't beat it on speed.
- **Audio's real value** = mining hours of talk for the occasional concrete disclosure — an exec
  revealing a launch date, a number, a partnership. Route these to a separate **"Signals / Overheard"**
  lane, clearly labeled and provenance-stamped — never mixed into the breaking market-event feed.
- Calling a podcast snippet "Breaking news" would mislabel commentary as fact and undo the signal work.

### Risks to design around (not blockers, but real)

- **Accuracy.** ASR mishears names and numbers ($50M↔$15M), and LLM extraction adds a second error
  layer. A wrong quote attributed to a real exec is a credibility-killer for a terminal product.
  Mitigate: confidence scores, mandatory timestamp+speaker provenance, human review before publishing
  exec claims, corroboration against text sources.
- **Copyright / ToS.** Republishing transcript chunks is a rights risk. Keep to short attributed
  quotes with a link back to the source; be aware of YouTube's terms on caption scraping.
- **Latency.** "The moment it launches" for audio realistically means *within ~10–30 min* (detect +
  transcribe + filter), not instant. Good enough for "interesting fact," not for genuine breaking.

## North star: the Bloomberg-terminal shape (what "more than news" means)

A terminal isn't "more headlines" — it's **structured, entity-linked, low-noise, queryable, real-time**.
That reframes the roadmap around four things beyond aggregation:

1. **Entity graph.** Every item linked to companies / people / regulators / products, so you can pull
   "everything on Stripe" or "APAC stablecoin actions this quarter." This is the terminal's spine.
2. **Lanes, not one feed.** Breaking market events · Regulatory actions · Signals/Overheard (audio) ·
   Data (on-chain, filings). Each lane has its own bar and cadence.
3. **Structured events.** Extract `{event_type, parties, amount, date, region}` — not just a headline —
   so items are filterable and comparable, and story clusters become timelines.
4. **Alerting / query.** "Notify me on any APAC licensing action" or "any funding round > $50M in payments."

Audio/video is **one input modality** feeding that graph — not a headline generator. Same for the
other new sources (filings, on-chain): they're inputs to the entity graph and the lanes.

## Phased rollout (each phase independently deployable; free parts first)

1. **Regions (free).** Ship `src/regions.py`; wire into `standalone_pipeline.py`; add `regions`/`primary_region`
   to `out/standalone/` and a region filter to the admin review queue. Zero LLM, zero risk.
2. **Sources + signal (free).** Add `sources.yaml` (Tier A/B/C), tier weighting, `consensus_count` from
   clustering, and the higher-signal gate. Still zero LLM.
3. **Tie-break (cheap LLM).** Add batched, prompt-cached Haiku for the REVIEW + region-unknown tail.
   Measure real cost against the estimate before scaling.
4. **Enrich (premium LLM, low volume).** Add the "so what" line on publishables (Sonnet). Optional:
   embeddings-based semantic dedup.
5. **Audio/video Signals lane.** Podcast-RSS + YouTube-WebSub detection → free-transcript-first →
   deterministic segment filter → Haiku extraction → the "Signals / Overheard" lane (separate from
   breaking). Ship detection + free-caption path first (cheap); add paid STT only for shows worth it.
6. **Terminal shape.** Entity graph + structured events + lanes + alerting/query. This is the
   Bloomberg-terminal north star; earlier phases feed it.

Phases 1–2 deliver regions + higher signal + more sources at **$0 LLM cost**. Only phases 3–4 spend,
and only on the tail. Production posting stays untouched until you choose to promote from the
standalone pipeline.
