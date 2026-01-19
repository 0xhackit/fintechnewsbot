import os
import sys
import json
import re
import html
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from telegram import Bot


OUT_DIR = Path("out")
CANDIDATES_JSON = OUT_DIR / "telegram_candidates.json"
APPROVED_JSON = OUT_DIR / "telegram_approved.json"


def _get_env(name: str) -> str:
    val = os.environ.get(name)
    if val is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    val = val.strip()
    if not val:
        raise RuntimeError(f"Environment variable {name} is set but empty")
    return val


def _iso_to_pretty(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        # Handles Z or +00:00
        s = iso.replace("Z", "+00:00")
        return datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%MZ")
    except Exception:
        return iso


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _load_items_last24h() -> list[dict]:
    path = OUT_DIR / "items_last24h.json"
    if not path.exists():
        raise RuntimeError("out/items_last24h.json not found. Run `python run.py` first.")
    items = json.loads(path.read_text(encoding="utf-8"))

    # Keep only dated items. Your pipeline stores dates in published_at.
    dated = [i for i in items if (i.get("published_at") or i.get("published_date"))]

    # Your pipeline already ranks by score, but keep a defensive sort.
    def key(i: dict):
        return (int(i.get("score") or 0), i.get("published_at") or i.get("published_date") or "")

    dated.sort(key=key, reverse=True)
    return dated


def _candidate_id(item: dict) -> str:
    # Stable-ish id for human selection
    link = (item.get("link") or "").strip()
    title = (item.get("title") or "").strip()
    base = (link or title).encode("utf-8", errors="ignore")
    # Simple non-crypto hash to keep stdlib-only
    h = 2166136261
    for b in base:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"


def prepare_candidates(limit: int = 30) -> list[dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    items = _load_items_last24h()[:limit]

    candidates = []
    for it in items:
        cid = _candidate_id(it)
        title = (it.get("title") or "").strip()
        link = (it.get("link") or it.get("url") or "").strip()
        score = int(it.get("score") or 0)
        published = it.get("published_at") or it.get("published_date")
        snippet = (it.get("summary") or it.get("snippet") or "").strip()
        topics = it.get("matched_topics") or []
        kws = it.get("matched_keywords") or []

        candidates.append(
            {
                "id": cid,
                "title": title,
                "link": link,
                "host": _host(link),
                "published_at": published,
                "score": score,
                "snippet": snippet,
                "matched_topics": topics,
                "matched_keywords": kws,
            }
        )

    CANDIDATES_JSON.write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also write a readable preview
    preview_lines = []
    preview_lines.append("TELEGRAM CANDIDATES (review + approve)\n")
    for idx, c in enumerate(candidates, 1):
        meta = f"score={c['score']} · {c.get('host','')} · { _iso_to_pretty(c.get('published_at')) }"
        preview_lines.append(f"{idx}. {c['title']}")
        preview_lines.append(f"   {meta}")
        if c.get("matched_topics"):
            preview_lines.append(f"   topics: {', '.join(c['matched_topics'][:3])}")
        if c.get("matched_keywords"):
            preview_lines.append(f"   keywords: {', '.join(c['matched_keywords'][:6])}")
        if c.get("link"):
            preview_lines.append(f"   {c['link']}")
        preview_lines.append("")

    (OUT_DIR / "telegram_candidates.txt").write_text("\n".join(preview_lines), encoding="utf-8")

    print(f"✅ Wrote candidates: {CANDIDATES_JSON}")
    print(f"✅ Wrote preview:   {OUT_DIR / 'telegram_candidates.txt'}")
    return candidates


def _parse_selection(s: str, n: int) -> list[int]:
    s = (s or "").strip().lower()
    if not s:
        return []
    if s in {"all", "a"}:
        return list(range(1, n + 1))

    out: set[int] = set()
    parts = [p.strip() for p in s.split(",") if p.strip()]
    for p in parts:
        if "-" in p:
            a, b = p.split("-", 1)
            try:
                lo = int(a)
                hi = int(b)
            except ValueError:
                continue
            if lo > hi:
                lo, hi = hi, lo
            for k in range(lo, hi + 1):
                if 1 <= k <= n:
                    out.add(k)
        else:
            try:
                k = int(p)
            except ValueError:
                continue
            if 1 <= k <= n:
                out.add(k)

    return sorted(out)


def approve_interactive(max_keep: int = 20) -> list[dict]:
    if not CANDIDATES_JSON.exists():
        prepare_candidates()

    candidates = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
    if not candidates:
        print("No candidates available.")
        return []

    print("\n" + "=" * 80)
    print("REVIEW CANDIDATES")
    print("Type numbers like: 1,3,5-8  (or 'all')")
    print("" + "=" * 80)

    for idx, c in enumerate(candidates, 1):
        meta = f"score={c['score']} · {c.get('host','')} · {_iso_to_pretty(c.get('published_at'))}"
        print(f"{idx:>2}. {c['title']}")
        print(f"    {meta}")

    sel = input(f"\nSelect up to {max_keep} to publish: ")
    picks = _parse_selection(sel, len(candidates))[:max_keep]

    approved = [candidates[i - 1] for i in picks]
    APPROVED_JSON.write_text(json.dumps(approved, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write a short preview of what will be sent
    (OUT_DIR / "telegram_approved.txt").write_text(_render_plain_preview(approved), encoding="utf-8")

    print(f"\n✅ Approved {len(approved)} items")
    print(f"✅ Wrote approved: {APPROVED_JSON}")
    print(f"✅ Preview:        {OUT_DIR / 'telegram_approved.txt'}")
    return approved


def _render_plain_preview(items: list[dict]) -> str:
    lines = []
    lines.append("TELEGRAM APPROVED (will publish)\n")
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. {it.get('title','')}")
        lines.append(f"   {_iso_to_pretty(it.get('published_at'))} · {it.get('host','')}")
        if it.get("link"):
            lines.append(f"   {it['link']}")
        lines.append("")
    return "\n".join(lines)


def _render_telegram_html(
    items: list[dict],
    title: str = "Digital Asset Intelligence — Last 24h",
    show_urls: bool = False,
) -> str:
    def esc(s: str) -> str:
        return html.escape(s or "")

    lines: list[str] = []
    lines.append(f"📊 <b>{esc(title)}</b>")
    lines.append("")

    for it in items:
        t = esc(it.get("title") or "")
        url = (it.get("link") or it.get("url") or "").strip()
        url_attr = html.escape(url, quote=True)
        host = esc(it.get("host") or "")

        if url:
            if show_urls:
                # For terminal previews: show the actual URL as text too.
                url_text = esc(url)
                lines.append(f"• <b>{t}</b> — <a href=\"{url_attr}\">LINK</a> <code>{url_text}</code>")
            else:
                # For publishing: keep URLs embedded.
                lines.append(f"• <b>{t}</b> — <a href=\"{url_attr}\">LINK</a>")
        else:
            lines.append(f"• <b>{t}</b>")

        # No dates in published format; keep a blank line between items
        lines.append("")

    s = "\n".join(lines).strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s


def _chunk_html(message: str, max_len: int = 3800) -> list[str]:
    # Chunk on line boundaries to avoid splitting tags.
    lines = message.split("\n")
    chunks: list[str] = []
    buf = ""
    for line in lines:
        cand = (buf + "\n" + line) if buf else line
        if len(cand) > max_len and buf:
            chunks.append(buf)
            buf = line
        else:
            buf = cand
    if buf:
        chunks.append(buf)
    return chunks


async def publish(items: list[dict]) -> None:
    token = _get_env("TELEGRAM_BOT_TOKEN")
    chat_id = _get_env("TELEGRAM_CHAT_ID")

    if not items:
        print("No items to publish.")
        return

    msg = _render_telegram_html(items, title="Bringing Fintech Onchain — Last 24h", show_urls=False)
    chunks = _chunk_html(msg)

    bot = Bot(token=token)
    for idx, chunk in enumerate(chunks, 1):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            print(f"❌ Failed to send chunk {idx}/{len(chunks)}: {e}")
            raise


def usage() -> None:
    print(
        "\n".join(
            [
                "Usage:",
                "  python scripts/publish_telegram.py --prepare       # build ranked candidate list",
                "  python scripts/publish_telegram.py --approve       # interactive pick -> out/telegram_approved.json",
                "  python scripts/publish_telegram.py --dry-run       # print what would be posted (approved if exists)",
                "  python scripts/publish_telegram.py --publish       # post approved items to Telegram",
                "",
                "Notes:",
                "  - Run `python run.py` first to refresh out/items_last24h.json",
                "  - Approved selections are stored in out/telegram_approved.json",
            ]
        )
    )


def dry_run() -> None:
    if APPROVED_JSON.exists():
        items = json.loads(APPROVED_JSON.read_text(encoding="utf-8"))
        print("\n[DRY RUN] Using approved items:\n")
    else:
        items = prepare_candidates()
        print("\n[DRY RUN] No approved file found; showing candidates:\n")

    msg = _render_telegram_html(items, title="Bringing Fintech Onchain — Last 24h", show_urls=True)
    print("\n" + "=" * 80)
    print(msg)
    print("=" * 80 + "\n")

def extract_html_from_issue_body(issue_body: str) -> str | None:
    """
    Extract the Telegram HTML draft from a GitHub issue body.
    Expects a fenced code block:
    ```html
    <b>Title</b> <a href="...">LINK</a>
    ```
    """
    if not issue_body:
        return None

    m = re.search(r"```html\\s*(.*?)\\s*```", issue_body, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()

def main_cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-issue-body", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables")

    if args.from_issue_body:
        issue_body = os.environ.get("ISSUE_BODY", "")
        html = extract_html_from_issue_body(issue_body)
        if not html:
            raise RuntimeError("Could not extract ```html``` draft from ISSUE_BODY")
        asyncio.run(send_html_message(token, chat_id, html))
        print("✅ Posted approved draft to Telegram.")
        return
        
    args = set(sys.argv[1:])
    if not args or "-h" in args or "--help" in args:
        usage()
        return

    if "--prepare" in args:
        prepare_candidates()
        return

    if "--approve" in args:
        approve_interactive()
        return

    if "--dry-run" in args:
        dry_run()
        return

    if "--publish" in args:
        if not APPROVED_JSON.exists():
            raise RuntimeError("out/telegram_approved.json not found. Run --approve first.")
        items = json.loads(APPROVED_JSON.read_text(encoding="utf-8"))
        asyncio.run(publish(items))
        return

    usage()


if __name__ == "__main__":
    main_cli()