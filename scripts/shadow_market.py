#!/usr/bin/env python3
"""
shadow_market.py — run the strict "market" editorial profile in shadow mode.

This is a SEPARATE, READ-ONLY feed for evaluating the stricter editorial policy
(src/editorial.py) WITHOUT touching the live bot. It does not post to Telegram
or X, does not write to state/, and does not modify any production output. It
only reads existing pipeline output and writes a side-by-side report under
out/market/<source>/.

Sources:
    feed     out/feed.json            the last N already-PUBLISHED items [default pair]
    items    out/items_last24h.json   the current live candidates

By default it generates BOTH so the frontend can toggle between them.

Output (out/market/<source>/):
    kept.json        kept stories with axis/reason
    killed.json      killed stories with axis/reason  (the noise you wanted gone)
    review.json      ambiguous stories to eyeball
    meta.json        {source, generated_at, total, keep, kill, review}
    digest.md        human-readable side-by-side report

Usage:
    python scripts/shadow_market.py                 # both sources
    python scripts/shadow_market.py --source feed   # published feed only
    python scripts/shadow_market.py --source items  # current candidates only
    python scripts/shadow_market.py --ai            # add Claude Haiku 2nd opinion
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import editorial  # noqa: E402

SOURCE_PATHS = {
    "items": _PROJECT_ROOT / "out" / "items_last24h.json",
    "feed": _PROJECT_ROOT / "out" / "feed.json",
}
SOURCE_LABELS = {"items": "Current candidates", "feed": "Published feed"}
OUT_ROOT = _PROJECT_ROOT / "out" / "market"

# Broad pipeline's publish gate (run_alerts.py MIN_ALERT_SCORE) — used only to
# label which killed items the live bot *would otherwise have surfaced*.
MIN_ALERT_SCORE = 35


def _load(path: Path):
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "entries" in data:
        return data["entries"]
    return data


def _norm(raw: dict) -> dict:
    """Normalize an item from either source into a common shape."""
    return {
        "title": (raw.get("title") or "").strip(),
        "link": (raw.get("link") or raw.get("url") or "").strip(),
        "snippet": (raw.get("snippet") or raw.get("summary") or "").strip(),
        "score": raw.get("score", 0),
        "category": raw.get("ai_category") or raw.get("category") or "",
    }


def run_one(source: str, use_ai: bool, limit: int, generated_at: str) -> dict | None:
    """Classify one source, write its report folder, return summary counts."""
    src_path = SOURCE_PATHS[source]
    raw_items = _load(src_path)
    if raw_items is None:
        print(f"⚠️  {source}: source not found ({src_path.name}), skipping")
        return None
    if limit:
        raw_items = raw_items[:limit]

    items = [_norm(r) for r in raw_items if (r.get("title") or "").strip()]
    print(f"\n📥 {SOURCE_LABELS[source]} — {src_path.name} ({len(items)} items)")

    kept, killed, review, ai_dis = [], [], [], []
    for it in items:
        verdict = editorial.classify(it["title"], it["snippet"])
        record = {**it, **verdict}
        if use_ai:
            ai = editorial.ai_second_opinion(it["title"], it["snippet"])
            if ai is not None:
                record.update(ai_publish=ai["publish"], ai_axis=ai["axis"], ai_reason=ai["reason"])
                if (verdict["verdict"] == editorial.KEEP) != ai["publish"]:
                    ai_dis.append(record)
        (kept if verdict["verdict"] == editorial.KEEP else
         killed if verdict["verdict"] == editorial.KILL else review).append(record)

    kept.sort(key=lambda r: r.get("score", 0), reverse=True)
    killed.sort(key=lambda r: r.get("score", 0), reverse=True)
    review.sort(key=lambda r: r.get("score", 0), reverse=True)
    killed_but_live = [k for k in killed if (k.get("score") or 0) >= MIN_ALERT_SCORE]

    out_dir = OUT_ROOT / source
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "kept.json").write_text(json.dumps(kept, indent=2, ensure_ascii=False))
    (out_dir / "killed.json").write_text(json.dumps(killed, indent=2, ensure_ascii=False))
    (out_dir / "review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False))

    meta = {
        "source": source,
        "label": SOURCE_LABELS[source],
        "generated_at": generated_at,
        "total": len(items),
        "keep": len(kept),
        "kill": len(killed),
        "review": len(review),
        "killed_but_live": len(killed_but_live),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    _write_digest(out_dir, src_path, items, kept, killed, review, killed_but_live, ai_dis, use_ai)

    total = len(items)
    print(f"   ✅ KEEP {len(kept)} ({_pct(len(kept), total)})"
          f"   🗑️ KILL {len(killed)} ({_pct(len(killed), total)}; "
          f"{len(killed_but_live)} ≥{MIN_ALERT_SCORE})"
          f"   🔎 REVIEW {len(review)} ({_pct(len(review), total)})")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["items", "feed", "both"], default="both")
    ap.add_argument("--limit", type=int, default=0, help="cap items processed (0 = all)")
    ap.add_argument("--ai", action="store_true", help="add Claude Haiku strict 2nd opinion")
    args = ap.parse_args()

    sources = ["feed", "items"] if args.source == "both" else [args.source]
    generated_at = datetime.now(timezone.utc).isoformat()

    produced = [run_one(s, args.ai, args.limit, generated_at) for s in sources]
    if not any(produced):
        print("\n❌ No sources produced output.")
        return 1
    print(f"\n📄 Reports under {OUT_ROOT}/<source>/   ·   view at /market")
    return 0


def _pct(n: int, total: int) -> str:
    return f"{(100 * n / total):.0f}%" if total else "0%"


def _line(r: dict) -> str:
    title = r.get("title", "")[:100]
    link = r.get("link", "")
    score = r.get("score", 0)
    axis = r.get("axis", "")
    matched = r.get("matched")
    trig = f" · `{matched}`" if matched else ""
    head = f"- **[{score}] {title}** — _{axis}_{trig}"
    ai = ""
    if "ai_publish" in r:
        flag = "keep" if r["ai_publish"] else "kill"
        ai = f"\n  - AI: **{flag}** ({r.get('ai_axis','')}) — {r.get('ai_reason','')}"
    url = f"\n  - {link}" if link else ""
    return head + ai + url


def _write_digest(out_dir, src_path, items, kept, killed, review, killed_but_live, ai_dis, use_ai):
    total = len(items)
    lines = [
        f"# Market profile — shadow report ({SOURCE_LABELS[out_dir.name]})",
        "",
        f"- **Source:** `{src_path.name}` ({total} items)",
        "- **Policy:** strict market profile (`src/editorial.py`) — keep concrete market events "
        "+ concrete regulatory actions; kill commentary / policy / political / low-signal.",
        "- **Mode:** read-only shadow. Nothing posted; live bot untouched.",
        "",
        "## Summary",
        "",
        "| Verdict | Count | Share |",
        "|---|---:|---:|",
        f"| ✅ KEEP | {len(kept)} | {_pct(len(kept), total)} |",
        f"| 🗑️ KILL | {len(killed)} | {_pct(len(killed), total)} |",
        f"| 🔎 REVIEW | {len(review)} | {_pct(len(review), total)} |",
        "",
        f"**{len(killed_but_live)}** killed stories scored ≥ {MIN_ALERT_SCORE} — i.e. the live "
        f"bot would have surfaced them. That's the noise this profile removes.",
        "",
    ]
    if use_ai and ai_dis:
        lines += [f"## ⚠️ AI vs deterministic disagreements ({len(ai_dis)})", ""]
        lines += [_line(r) for r in ai_dis] + [""]

    lines += [f"## 🗑️ KILLED ({len(killed)}) — the noise removed", ""]
    if killed:
        for axis in ["commentary", "policy", "political", "low_signal"]:
            group = [k for k in killed if k.get("axis") == axis]
            if group:
                lines.append(f"### {axis} ({len(group)})")
                lines += [_line(r) for r in group]
                lines.append("")
    else:
        lines += ["_none_", ""]

    lines += [f"## ✅ KEPT ({len(kept)}) — the market feed", ""]
    lines += ([_line(r) for r in kept] if kept else ["_none_"]) + [""]
    lines += [f"## 🔎 REVIEW ({len(review)}) — ambiguous, eyeball these", ""]
    lines += ([_line(r) for r in review] if review else ["_none_"]) + [""]
    (out_dir / "digest.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
