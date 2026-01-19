# Fintech News MVP (Phase 1)

Daily reliable fintech news feed using **Google News RSS**.

## What it does
- Pulls from Google News RSS feed URL(s) in `config.json`
- Normalizes items (HTML strip, URL canonicalization, date parsing)
- Keyword + topic matching
- Keeps items from the last N hours (default 24h)
- Hard-dedupes by canonical URL
- Outputs:
  - `out/items_last24h.json`
  - `out/digest.md`

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt