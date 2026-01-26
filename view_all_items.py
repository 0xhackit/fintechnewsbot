#!/usr/bin/env python3
"""
View All Scraped Items - Interactive viewer for all news items
Shows ALL items including filtered ones, with scores and metadata
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import sys

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

def load_drafts() -> List[Dict]:
    """Load current alert drafts"""
    drafts_path = Path('out/alerts_drafts.json')
    if drafts_path.exists():
        return json.loads(drafts_path.read_text())
    return []

def format_item(item: Dict, index: int, state: Dict, drafts: List[Dict]) -> str:
    """Format item for display"""
    item_id = item.get('id', 'unknown')
    score = item.get('score', 0)
    title = item.get('title', 'Untitled')
    url = item.get('url', '')
    source = item.get('feed_name', item.get('source', 'Unknown'))
    topics = item.get('matched_topics', [])
    keywords = item.get('matched_keywords', [])
    published = item.get('published_at', '')

    # Check status
    is_seen = item_id in state.get('seen', [])
    is_draft = any(d['id'] == item_id for d in drafts)

    # Status indicators
    status_parts = []
    if is_draft:
        status_parts.append('📤 DRAFT')
    if is_seen:
        status_parts.append('👁️  SEEN')
    if score >= 35:
        status_parts.append('✅ PASSES')
    else:
        status_parts.append('❌ FILTERED')

    status = ' | '.join(status_parts) if status_parts else 'NEW'

    # Format output
    output = f"\n{'='*80}\n"
    output += f"[{index}] Score: {score} | {status}\n"
    output += f"Title: {title}\n"
    output += f"Source: {source} | Published: {published[:10] if published else 'Unknown'}\n"
    if topics:
        output += f"Topics: {', '.join(topics)}\n"
    if keywords:
        output += f"Keywords: {', '.join(keywords[:5])}\n"
    output += f"URL: {url[:80]}...\n" if len(url) > 80 else f"URL: {url}\n"
    output += f"ID: {item_id[:16]}...\n"

    return output

def filter_items(items: List[Dict], args: Dict) -> List[Dict]:
    """Filter items based on criteria"""
    filtered = items

    # Filter by score range
    if args.get('min_score') is not None:
        filtered = [i for i in filtered if i.get('score', 0) >= args['min_score']]
    if args.get('max_score') is not None:
        filtered = [i for i in filtered if i.get('score', 0) <= args['max_score']]

    # Filter by topic
    if args.get('topic'):
        topic = args['topic'].lower()
        filtered = [
            i for i in filtered
            if any(topic in t.lower() for t in i.get('matched_topics', []))
        ]

    # Filter by keyword
    if args.get('keyword'):
        keyword = args['keyword'].lower()
        filtered = [
            i for i in filtered
            if any(keyword in k.lower() for k in i.get('matched_keywords', []))
            or keyword in i.get('title', '').lower()
        ]

    # Filter by status
    if args.get('status'):
        state = load_state()
        drafts = load_drafts()
        status = args['status'].lower()

        if status == 'seen':
            filtered = [i for i in filtered if i.get('id') in state.get('seen', [])]
        elif status == 'unseen':
            filtered = [i for i in filtered if i.get('id') not in state.get('seen', [])]
        elif status == 'draft':
            draft_ids = {d['id'] for d in drafts}
            filtered = [i for i in filtered if i.get('id') in draft_ids]
        elif status == 'filtered':
            filtered = [i for i in filtered if i.get('score', 0) < 35]
        elif status == 'passes':
            filtered = [i for i in filtered if i.get('score', 0) >= 35]

    return filtered

def display_summary(items: List[Dict], state: Dict, drafts: List[Dict]):
    """Display summary statistics"""
    total = len(items)

    # Score distribution
    score_ranges = {
        '80+': len([i for i in items if i.get('score', 0) >= 80]),
        '50-79': len([i for i in items if 50 <= i.get('score', 0) < 80]),
        '35-49': len([i for i in items if 35 <= i.get('score', 0) < 50]),
        '<35': len([i for i in items if i.get('score', 0) < 35]),
    }

    # Status counts
    seen_count = len([i for i in items if i.get('id') in state.get('seen', [])])
    draft_count = len([i for i in items if any(d['id'] == i.get('id') for d in drafts)])
    passes_count = len([i for i in items if i.get('score', 0) >= 35])

    print("\n" + "="*80)
    print("📊 SCRAPED DATA SUMMARY")
    print("="*80)
    print(f"Total items: {total}")
    print(f"\nScore Distribution:")
    for range_name, count in score_ranges.items():
        print(f"  {range_name}: {count}")
    print(f"\nStatus:")
    print(f"  ✅ Passes filter (≥35): {passes_count}")
    print(f"  ❌ Filtered out (<35): {total - passes_count}")
    print(f"  👁️  Already seen: {seen_count}")
    print(f"  📤 In drafts: {draft_count}")
    print("="*80 + "\n")

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='View all scraped news items with filtering options',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View all items
  python view_all_items.py

  # View only filtered items (score < 35)
  python view_all_items.py --status filtered

  # View items with score 30-40
  python view_all_items.py --min-score 30 --max-score 40

  # View items about tokenization
  python view_all_items.py --topic tokenized

  # View items mentioning "bitcoin"
  python view_all_items.py --keyword bitcoin

  # View unseen items sorted by score
  python view_all_items.py --status unseen --sort score
        """
    )

    parser.add_argument('--min-score', type=int, help='Minimum score')
    parser.add_argument('--max-score', type=int, help='Maximum score')
    parser.add_argument('--topic', help='Filter by topic (partial match)')
    parser.add_argument('--keyword', help='Filter by keyword (partial match)')
    parser.add_argument('--status', choices=['seen', 'unseen', 'draft', 'filtered', 'passes'],
                       help='Filter by status')
    parser.add_argument('--sort', choices=['score', 'date', 'title'], default='score',
                       help='Sort by (default: score)')
    parser.add_argument('--limit', type=int, help='Limit number of results')
    parser.add_argument('--summary-only', action='store_true',
                       help='Show only summary statistics')
    parser.add_argument('--export-ids', help='Export matching item IDs to file')

    args = parser.parse_args()

    # Load data
    print("📡 Loading scraped data...")
    items = load_items()
    state = load_state()
    drafts = load_drafts()

    # Display summary
    display_summary(items, state, drafts)

    if args.summary_only:
        return

    # Apply filters
    filter_args = {
        'min_score': args.min_score,
        'max_score': args.max_score,
        'topic': args.topic,
        'keyword': args.keyword,
        'status': args.status,
    }
    filtered = filter_items(items, filter_args)

    # Sort
    if args.sort == 'score':
        filtered.sort(key=lambda x: x.get('score', 0), reverse=True)
    elif args.sort == 'date':
        filtered.sort(key=lambda x: x.get('published_at', ''), reverse=True)
    elif args.sort == 'title':
        filtered.sort(key=lambda x: x.get('title', ''))

    # Apply limit
    if args.limit:
        filtered = filtered[:args.limit]

    # Display results
    if filtered:
        print(f"🔍 Found {len(filtered)} items matching filters\n")
        for i, item in enumerate(filtered, 1):
            print(format_item(item, i, state, drafts))
    else:
        print("❌ No items match the filters")

    # Export IDs if requested
    if args.export_ids and filtered:
        ids = [item.get('id') for item in filtered]
        export_path = Path(args.export_ids)
        export_path.write_text(json.dumps(ids, indent=2))
        print(f"\n✅ Exported {len(ids)} item IDs to {args.export_ids}")

if __name__ == '__main__':
    main()
