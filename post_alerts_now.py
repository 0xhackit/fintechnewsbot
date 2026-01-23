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
from pathlib import Path
from telegram import Bot


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

    for i, draft in enumerate(drafts, 1):
        message = draft.get('message_html', '')
        title = draft.get('title', '')

        if not message:
            print(f"⚠️  Skipping {i}/{len(drafts)}: No message HTML")
            continue

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            print(f"✅ {i}/{len(drafts)}: {title[:70]}...")
        except Exception as e:
            print(f"❌ {i}/{len(drafts)}: Failed - {e}")
            print(f"   Title: {title[:70]}...")

    print(f"\n🎉 Done! Posted {len(drafts)} alerts to Telegram")


if __name__ == "__main__":
    asyncio.run(post_drafts())
