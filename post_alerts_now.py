#!/usr/bin/env python3
"""
Quick script to post the generated alerts to Telegram.

Usage:
    export TELEGRAM_BOT_TOKEN="your_bot_token_here"
    export TELEGRAM_CHAT_ID="your_chat_id_here"
    python3 post_alerts_now.py
"""
import json
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from telegram import Bot
from feed_writer import write_entries_to_feed

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]


def _load_config() -> dict:
    """Load config.json from repo root."""
    config_path = Path(__file__).resolve().parent / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _fetch_trade_analysis(article_url: str) -> str | None:
    """Call the frontend /api/analyze endpoint and format as Telegram HTML."""
    if _requests is None:
        return None

    frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not frontend_url or not article_url:
        return None

    try:
        resp = _requests.post(
            f"{frontend_url}/api/analyze",
            json={"url": article_url},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ⚠️  Analysis API returned {resp.status_code}")
            return None

        data = resp.json()
        analysis = data.get("analysis", {})
        price = data.get("price", {})

        ticker = analysis.get("ticker", "N/A")
        short_term = analysis.get("shortTerm", {})
        long_term = analysis.get("longTerm", {})
        direction = short_term.get("direction", "NEUTRAL")
        conf = short_term.get("confidence", 5)
        summary = analysis.get("summary", "")

        lt_direction = long_term.get("direction", "NEUTRAL")
        lt_horizon = long_term.get("timeHorizon", "1-3 months")

        # Format price
        price_val = price.get("price")
        price_str = ""
        if price_val and price_val >= 1:
            price_str = f" ${price_val:,.0f}"
        elif price_val:
            price_str = f" ${price_val:.4f}"

        arrow = "▲" if direction == "LONG" else "▼" if direction == "SHORT" else "—"
        lt_arrow = "▲" if lt_direction == "LONG" else "▼" if lt_direction == "SHORT" else "—"

        # Build Telegram HTML message
        lines = [
            f"<b>AI Trade Signal: ${ticker}{price_str}</b>",
            f"{arrow} {direction} ({conf}/10 confidence)",
            "",
        ]

        target = short_term.get("targetPrice")
        stop = short_term.get("stopLoss")
        if target:
            target_str = f"${target:,.0f}" if target >= 1 else f"${target:.4f}"
            line = f"Short-term: Target {target_str}"
            if stop:
                stop_str = f"${stop:,.0f}" if stop >= 1 else f"${stop:.4f}"
                line += f", Stop {stop_str}"
            lines.append(line)

        lines.append(f"Long-term: {lt_arrow} {lt_direction} ({lt_horizon})")

        if summary:
            lines.append("")
            lines.append(summary[:200])

        return "\n".join(lines)

    except Exception as e:
        print(f"  ⚠️  Analysis fetch failed: {e}")
        return None


async def post_drafts():
    # Get credentials from environment
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not token or not chat_id:
        print("❌ Error: Missing environment variables")
        print("\nPlease set:")
        print("  export TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("  export TELEGRAM_CHAT_ID='your_chat_id'")
        sys.exit(1)

    # Load config for feature flags
    config = _load_config()
    alerts_config = config.get("alerts", {})
    analysis_on_telegram = alerts_config.get("trade_analysis_telegram", False)

    # Load drafts
    drafts_path = Path('out/alerts_drafts.json')
    if not drafts_path.exists():
        print("❌ No alerts_drafts.json found")
        sys.exit(1)

    drafts = json.loads(drafts_path.read_text())

    if not drafts:
        print("📭 No alerts to post")
        return

    print(f"📤 Posting {len(drafts)} alerts to Telegram...\n")
    if analysis_on_telegram:
        print("📊 Trade analysis replies enabled for Telegram")

    bot = Bot(token=token)
    feed_entries = []

    for i, draft in enumerate(drafts, 1):
        message = draft.get('message_html', '')
        title = draft.get('title', '')

        if not message:
            print(f"⚠️  Skipping {i}/{len(drafts)}: No message HTML")
            continue

        try:
            result_msg = await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            msg_id = result_msg.message_id
            posted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"✅ {i}/{len(drafts)}: {title[:70]}...")

            # Post AI trade analysis as a reply (if enabled)
            if analysis_on_telegram:
                article_link = draft.get("link", "")
                analysis_text = _fetch_trade_analysis(article_link)
                if analysis_text:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=analysis_text,
                            parse_mode='HTML',
                            disable_web_page_preview=True,
                            reply_to_message_id=msg_id,
                        )
                        print(f"  📊 Analysis reply posted")
                    except Exception as e:
                        print(f"  ⚠️  Analysis reply failed: {e}")

            feed_entries.append({
                "id": draft.get("id", ""),
                "title": title,
                "link": draft.get("link", ""),
                "snippet": draft.get("snippet", ""),
                "score": draft.get("score", 0),
                "matched_topics": draft.get("matched_topics", []),
                "ai_category": draft.get("ai_category", ""),
                "ai_priority": draft.get("ai_priority", ""),
                "posted_at": posted_at,
                "source": draft.get("source", ""),
                "feed_name": draft.get("feed_name", ""),
                "published_at": draft.get("published_at", ""),
                "posted_to_telegram": True,
                "telegram_message_id": msg_id,
                "posted_to_x": False,
                "tweet_id": None,
                "tweet_text": None,
                "tweet_url": None,
            })
        except Exception as e:
            print(f"❌ {i}/{len(drafts)}: Failed - {e}")
            print(f"   Title: {title[:70]}...")

    # Write feed entries (TG-only at this point; X script will upsert tweet data)
    if feed_entries:
        write_entries_to_feed(feed_entries)

    print(f"\n🎉 Done! Posted {len(drafts)} alerts to Telegram")


if __name__ == "__main__":
    asyncio.run(post_drafts())
