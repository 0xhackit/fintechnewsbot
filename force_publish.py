#!/usr/bin/env python3
"""
Force Publish - Manual override to publish specific items
Bypasses score filters and seen state to force-post items to Telegram
"""

import json
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import sys

try:
    from telegram import Bot
except ImportError:
    print("❌ telegram module not found. Install: pip install python-telegram-bot")
    sys.exit(1)

def load_items() -> List[Dict]:
    """Load all items from items_last24h.json"""
    items_path = Path('out/items_last24h.json')
    if not items_path.exists():
        print("❌ No items file found at out/items_last24h.json")
        print("Run 'python run.py' first to fetch news")
        sys.exit(1)

    return json.loads(items_path.read_text())

def load_state() -> Dict:
    """Load seen state"""
    state_path = Path('state/seen_alerts.json')
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {'seen': [], 'seen_titles': []}

def save_state(state: Dict):
    """Save updated state"""
    state_path = Path('state/seen_alerts.json')
    state_path.write_text(json.dumps(state, indent=2))

def find_items_by_ids(items: List[Dict], item_ids: List[str]) -> List[Dict]:
    """Find items matching the given IDs"""
    # Support both full IDs and partial IDs (first 16 chars)
    found = []
    for item in items:
        item_id = item.get('id', '')
        for search_id in item_ids:
            if item_id == search_id or item_id.startswith(search_id):
                found.append(item)
                break

    return found

def find_items_by_indices(items: List[Dict], indices: List[int]) -> List[Dict]:
    """Find items by their index numbers (1-based, sorted by score)"""
    # Sort items by score (matching view_all_items.py default)
    sorted_items = sorted(items, key=lambda x: x.get('score', 0), reverse=True)

    found = []
    for idx in indices:
        if 1 <= idx <= len(sorted_items):
            found.append(sorted_items[idx - 1])
        else:
            print(f"⚠️  Index {idx} out of range (1-{len(sorted_items)})")

    return found

def create_alert_message(item: Dict) -> str:
    """Create formatted Telegram message for an item"""
    title = item.get('title', 'Untitled')
    url = item.get('url', '')
    snippet = item.get('snippet', '')
    source = item.get('feed_name', item.get('source', 'Unknown'))
    score = item.get('score', 0)

    # Format message with HTML
    message = f"<b>{title}</b>\n\n"

    if snippet:
        message += f"{snippet}\n\n"

    message += f"<a href=\"{url}\">Read more</a>"
    message += f" | Score: {score} | Source: {source}"

    # Add manual override indicator
    message += f"\n\n🔧 <i>Manually published</i>"

    return message

async def post_to_telegram(items: List[Dict], dry_run: bool = False):
    """Post items to Telegram"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not token or not chat_id:
        print("❌ Missing environment variables:")
        if not token:
            print("   - TELEGRAM_BOT_TOKEN")
        if not chat_id:
            print("   - TELEGRAM_CHAT_ID")
        print("\nSet them with:")
        print('  export TELEGRAM_BOT_TOKEN="your_token"')
        print('  export TELEGRAM_CHAT_ID="your_chat_id"')
        sys.exit(1)

    bot = Bot(token=token)

    print(f"\n{'='*80}")
    print(f"📤 {'DRY RUN - ' if dry_run else ''}Posting {len(items)} item(s) to Telegram")
    print(f"{'='*80}\n")

    for i, item in enumerate(items, 1):
        title = item.get('title', 'Untitled')
        score = item.get('score', 0)
        url = item.get('url', '')

        print(f"[{i}/{len(items)}] {title[:60]}...")
        print(f"  Score: {score} | URL: {url[:60]}...")

        message = create_alert_message(item)

        if dry_run:
            print("  🔍 DRY RUN - Message preview:")
            print("  " + "-"*76)
            # Show plain text version
            plain = message.replace('<b>', '').replace('</b>', '')
            plain = plain.replace('<i>', '').replace('</i>', '')
            plain = plain.replace('<a href="', '').replace('">', ' ').replace('</a>', '')
            for line in plain.split('\n'):
                print(f"  {line}")
            print("  " + "-"*76)
        else:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                print("  ✅ Posted successfully")
                await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"  ❌ Failed to post: {e}")

        print()

def mark_as_seen(items: List[Dict]):
    """Mark items as seen in state file"""
    state = load_state()

    for item in items:
        item_id = item.get('id')
        title = item.get('title', '')

        if item_id not in state['seen']:
            state['seen'].append(item_id)

        # Add to seen_titles if not exists
        if not any(t.get('id') == item_id for t in state['seen_titles']):
            state['seen_titles'].append({
                'id': item_id,
                'title': title,
                'seen_at': datetime.now().isoformat()
            })

    save_state(state)
    print(f"✅ Marked {len(items)} item(s) as seen in state file")

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Force publish specific items to Telegram (bypass filters)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View items first to get indices or IDs
  python view_all_items.py --status filtered

  # Force publish items by index (1-based, from view_all_items.py)
  python force_publish.py --indices 1 2 5

  # Force publish by item ID
  python force_publish.py --ids 8325bccdff7e19d7 2939940cd8002d2e

  # Force publish from a file of IDs
  python force_publish.py --ids-file selected_ids.json

  # Dry run (preview without posting)
  python force_publish.py --indices 1 2 --dry-run

  # Post without marking as seen (can repost later)
  python force_publish.py --indices 1 --no-mark-seen
        """
    )

    parser.add_argument('--indices', nargs='+', type=int,
                       help='Item indices to publish (1-based, from view_all_items.py)')
    parser.add_argument('--ids', nargs='+',
                       help='Item IDs to publish (full or partial)')
    parser.add_argument('--ids-file', help='JSON file containing item IDs')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview messages without posting')
    parser.add_argument('--no-mark-seen', action='store_true',
                       help='Do not mark items as seen (can repost later)')

    args = parser.parse_args()

    # Validate inputs
    if not any([args.indices, args.ids, args.ids_file]):
        parser.error("Must specify --indices, --ids, or --ids-file")

    # Load items
    print("📡 Loading scraped data...")
    items = load_items()
    print(f"✅ Loaded {len(items)} items")

    # Find items to publish
    to_publish = []

    if args.indices:
        print(f"\n🔍 Finding items by indices: {args.indices}")
        found = find_items_by_indices(items, args.indices)
        to_publish.extend(found)
        print(f"✅ Found {len(found)} items")

    if args.ids:
        print(f"\n🔍 Finding items by IDs: {[id[:16] for id in args.ids]}")
        found = find_items_by_ids(items, args.ids)
        to_publish.extend(found)
        print(f"✅ Found {len(found)} items")

    if args.ids_file:
        print(f"\n🔍 Loading IDs from {args.ids_file}")
        ids_path = Path(args.ids_file)
        if not ids_path.exists():
            print(f"❌ File not found: {args.ids_file}")
            sys.exit(1)

        ids = json.loads(ids_path.read_text())
        found = find_items_by_ids(items, ids)
        to_publish.extend(found)
        print(f"✅ Found {len(found)} items")

    # Remove duplicates
    seen_ids = set()
    unique = []
    for item in to_publish:
        item_id = item.get('id')
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            unique.append(item)
    to_publish = unique

    if not to_publish:
        print("\n❌ No items found matching the criteria")
        sys.exit(1)

    # Display items to publish
    print(f"\n{'='*80}")
    print(f"📋 Items to publish ({len(to_publish)}):")
    print(f"{'='*80}")
    for i, item in enumerate(to_publish, 1):
        title = item.get('title', 'Untitled')
        score = item.get('score', 0)
        print(f"[{i}] Score {score}: {title[:70]}")
    print(f"{'='*80}\n")

    # Confirm unless dry run
    if not args.dry_run:
        confirm = input("Proceed with posting? [y/N]: ")
        if confirm.lower() != 'y':
            print("❌ Cancelled")
            sys.exit(0)

    # Post to Telegram
    asyncio.run(post_to_telegram(to_publish, dry_run=args.dry_run))

    # Mark as seen
    if not args.no_mark_seen and not args.dry_run:
        mark_as_seen(to_publish)

    print("\n✅ Done!")
    if args.dry_run:
        print("💡 Run without --dry-run to actually post")

if __name__ == '__main__':
    main()
