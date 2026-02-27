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
