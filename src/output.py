import json
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict


def write_json(path: str, items: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def write_markdown_digest(
    path: str,
    now_utc: datetime,
    lookback_hours: int,
    windowed: List[Dict[str, Any]],
    undated: List[Dict[str, Any]],
    topics: List[Dict[str, Any]],
) -> None:
    # Group dated items by topic name (first matched topic), fallback "Other"
    by_topic = defaultdict(list)
    for it in windowed:
        t = (it.get("matched_topics") or [])
        key = t[0] if t else "Other"
        by_topic[key].append(it)

    # Keep stable topic order from config, then Other
    ordered_topics = [t.get("name") for t in topics if t.get("name")]
    if "Other" not in ordered_topics:
        ordered_topics.append("Other")

    lines = []
    lines.append(f"# Fintech News Digest (Last {lookback_hours}h)")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{now_utc.isoformat()}`")
    lines.append(f"- Items (dated): **{len(windowed)}**")
    lines.append(f"- Items (undated): **{len(undated)}**")
    lines.append("")

    def fmt_item(it: Dict[str, Any]) -> str:
        title = it.get("title", "").strip()
        url = it.get("canonical_url") or it.get("url")
        src = it.get("source", "Unknown")
        pub = it.get("published_at")
        pub_str = pub[:19] + "Z" if pub else "undated"
        return f"- **{title}**  \n  _{src} · {pub_str}_  \n  {url}"

    # Dated section
    lines.append("## Dated (within window)")
    lines.append("")
    for topic in ordered_topics:
        items = by_topic.get(topic, [])
        if not items:
            continue
        lines.append(f"### {topic}")
        lines.append("")
        for it in items:
            lines.append(fmt_item(it))
        lines.append("")

    # Undated section
    if undated:
        lines.append("## Undated (fetched this run)")
        lines.append("")
        for it in undated:
            lines.append(fmt_item(it))
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))