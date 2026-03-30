#!/usr/bin/env python3
"""
Post approved alerts to X (Twitter) using the v2 API.

Features:
  - News-wire format: posts article title with @company handles
  - OG image fetching: attaches article images for higher engagement
  - Daily rate guard: caps posts at 40/day (free tier = 50/day)
  - Ranking agent integration: uses post_to_x flag from run_alerts.py
  - Dry-run mode: test everything without posting
"""
import os
import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin
import requests

# Ensure repo root is on sys.path so we can import feed_writer and src modules
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from feed_writer import write_entries_to_feed
from src.utils import canonicalize_url, normalize_title, tokenize_title, jaccard_similarity, extract_entities


# ===========================================================================
# Company @handle mapping (for AI tweet generation)
# ===========================================================================

COMPANY_HANDLES = {
    "coinbase": "@coinbase",
    "stripe": "@stripe",
    "circle": "@circle",
    "ripple": "@Ripple",
    "paypal": "@PayPal",
    "visa": "@Visa",
    "mastercard": "@Mastercard",
    "jpmorgan": "@jpmorgan",
    "jp morgan": "@jpmorgan",
    "blackrock": "@BlackRock",
    "fidelity": "@Fidelity",
    "revolut": "@RevolutApp",
    "plaid": "@PlaidDev",
    "robinhood": "@RobinhoodApp",
    "kraken": "@kaboracle",
    "binance": "@binance",
    "gemini": "@Gemini",
    "square": "@Square",
    "block": "@blocks",
    "wise": "@wise",
    "klarna": "@Klarna",
    "affirm": "@Affirm",
    "sofi": "@SoFi",
    "brex": "@brex",
    "ubs": "@UBS",
    "hsbc": "@HSBC",
    "goldman sachs": "@GoldmanSachs",
    "goldman": "@GoldmanSachs",
    "morgan stanley": "@MorganStanley",
    "deutsche bank": "@DeutscheBank",
    "barclays": "@Barclays",
    "standard chartered": "@StanChart",
    "citi": "@Citi",
    "citigroup": "@Citi",
    "bnp paribas": "@BNPParibas",
    "societe generale": "@SocieteGenerale",
    "bank of america": "@BankofAmerica",
    "wells fargo": "@WellsFargo",
    "state street": "@StateStreet",
    "bny mellon": "@BNYMellon",
    "franklin templeton": "@FTI_US",
    "anchorage": "@Anchorage",
    "paxos": "@PaxosGlobal",
    "bitstamp": "@Bitstamp",
    "bybit": "@Bybit_Official",
    "okx": "@okx",
    "tether": "@Tether_to",
}

# ===========================================================================
# Environment + config helpers
# ===========================================================================

def _get_env(name: str, required: bool = True) -> Optional[str]:
    """Get environment variable, raise if required and missing."""
    val = os.environ.get(name)
    if required and val is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    if val:
        val = val.strip()
        if required and not val:
            raise RuntimeError(f"Environment variable {name} is set but empty")
    return val


def _load_config() -> dict:
    """Load config.json, return empty dict on failure."""
    config_path = Path("config.json")
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ===========================================================================
# Twitter API v2 posting
# ===========================================================================

def _post_to_x(text: str, api_key: str, api_secret: str,
               access_token: str, access_secret: str,
               media_ids: list[str] = None,
               reply_to_id: str = None) -> dict:
    """Post a tweet using Twitter API v2 with OAuth 1.0a User Context."""
    try:
        from requests_oauthlib import OAuth1
    except ImportError:
        raise RuntimeError(
            "requests-oauthlib is required for X posting. "
            "Install with: pip install requests-oauthlib"
        )

    url = "https://api.twitter.com/2/tweets"
    auth = OAuth1(api_key, api_secret, access_token, access_secret)
    payload = {"text": text}

    if media_ids:
        payload["media"] = {"media_ids": media_ids}
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

    response = requests.post(
        url, auth=auth, json=payload,
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 402:
        raise RuntimeError(
            f"X API Credits Depleted. Free Tier limits: 1,500 posts/month (50/day). "
            f"Check https://developer.twitter.com/en/portal/dashboard\n"
            f"Original error: {response.text}"
        )

    if response.status_code == 403:
        error_detail = response.json().get('detail', response.text)
        if 'oauth1-permissions' in error_detail.lower():
            raise RuntimeError(
                f"X API Permission Error: App needs 'Read and Write' OAuth 1.0a permissions.\n"
                f"Fix at: https://developer.twitter.com/en/portal/projects-and-apps\n"
                f"Original error: {response.text}"
            )
        raise RuntimeError(f"X API error 403: {response.text}")

    if response.status_code not in (200, 201):
        raise RuntimeError(f"X API error {response.status_code}: {response.text}")

    return response.json()


# ===========================================================================
# AI Trade Analysis Reply
# ===========================================================================

def _post_analysis_reply(tweet_id: str, article_url: str,
                         api_key: str, api_secret: str,
                         access_token: str, access_secret: str,
                         dry_run: bool = False) -> None:
    """Post AI trade analysis as a reply to the article tweet.

    Calls the frontend /api/analyze endpoint and formats the result
    as a concise reply tweet with ticker, direction, and summary.
    """
    frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not frontend_url:
        return

    if not article_url:
        return

    try:
        print(f"  📊 Fetching AI trade analysis...")
        resp = requests.post(
            f"{frontend_url}/api/analyze",
            json={"url": article_url},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ⚠️  Analysis API returned {resp.status_code}")
            return

        data = resp.json()
        analysis = data.get("analysis", {})
        price = data.get("price", {})

        # Extract fields
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
        price_str = f" ${price_val:,.0f}" if price_val and price_val >= 1 else ""
        if price_val and price_val < 1:
            price_str = f" ${price_val:.4f}"

        # Direction arrows
        arrow = "▲" if direction == "LONG" else "▼" if direction == "SHORT" else "—"
        lt_arrow = "▲" if lt_direction == "LONG" else "▼" if lt_direction == "SHORT" else "—"

        # Build reply tweet (keep under 280 chars)
        lines = [
            f"AI Trade Signal: ${ticker}{price_str}",
            f"{arrow} {direction} ({conf}/10 confidence)",
            "",
        ]

        # Add short-term targets if available
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
            # Trim summary to fit
            remaining = 280 - len("\n".join(lines)) - 2
            if remaining > 30:
                lines.append("")
                lines.append(summary[:remaining])

        reply_text = "\n".join(lines)

        # Truncate to 280 chars
        if len(reply_text) > 280:
            reply_text = reply_text[:277] + "..."

        if dry_run:
            print(f"  📊 [DRY RUN] Analysis reply:\n{reply_text}")
            return

        _post_to_x(
            reply_text,
            api_key, api_secret, access_token, access_secret,
            reply_to_id=tweet_id,
        )
        print(f"  📊 Analysis reply posted (${ticker} {direction})")

    except Exception as e:
        print(f"  ⚠️  Analysis reply failed: {e}")


# ===========================================================================
# OG image fetching + media upload
# ===========================================================================

def _fetch_og_image(article_url: str) -> Optional[bytes]:
    """
    Fetch the og:image from an article URL.
    Returns image bytes or None on failure.
    """
    try:
        resp = requests.get(article_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FintechNewsBot/1.0)"
        })
        resp.raise_for_status()

        # Parse og:image from HTML
        match = re.search(
            r'<meta\s+(?:[^>]*?)property=["\']og:image["\'][^>]*?content=["\']([^"\']+)["\']',
            resp.text, re.IGNORECASE
        )
        if not match:
            # Try reversed attribute order
            match = re.search(
                r'<meta\s+(?:[^>]*?)content=["\']([^"\']+)["\'][^>]*?property=["\']og:image["\']',
                resp.text, re.IGNORECASE
            )
        if not match:
            return None

        image_url = match.group(1).strip()
        # Handle relative URLs
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        elif not image_url.startswith("http"):
            image_url = urljoin(article_url, image_url)

        # Download image
        img_resp = requests.get(image_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FintechNewsBot/1.0)"
        })
        img_resp.raise_for_status()

        content_type = img_resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return None

        # Sanity check: skip tiny images (likely tracking pixels) or huge images
        img_bytes = img_resp.content
        if len(img_bytes) < 5_000 or len(img_bytes) > 5_000_000:
            return None

        return img_bytes

    except Exception as e:
        print(f"  ⚠️  OG image fetch failed: {e}")
        return None


def _upload_media(image_bytes: bytes, api_key: str, api_secret: str,
                  access_token: str, access_secret: str) -> Optional[str]:
    """
    Upload image to Twitter v1.1 media endpoint.
    Returns media_id_string or None on failure.
    """
    try:
        from requests_oauthlib import OAuth1
    except ImportError:
        return None

    url = "https://upload.twitter.com/1.1/media/upload.json"
    auth = OAuth1(api_key, api_secret, access_token, access_secret)

    response = requests.post(
        url, auth=auth,
        files={"media_data": ("image.jpg", image_bytes, "application/octet-stream")},
    )

    if response.status_code not in (200, 201, 202):
        print(f"  ⚠️  Media upload failed ({response.status_code}): {response.text[:200]}")
        return None

    media_id = response.json().get("media_id_string")
    return media_id


# ===========================================================================
# Tweet formatting
# ===========================================================================

def _format_news_tweet(draft: dict) -> str:
    """Format a news-wire style tweet from the article title.
    Replaces one company name with its @handle for engagement."""
    title = (draft.get("title") or "").strip()

    # Replace one company name with its @handle
    for company, handle in COMPANY_HANDLES.items():
        pattern = re.compile(rf'\b{re.escape(company)}\b', re.IGNORECASE)
        if pattern.search(title):
            title = pattern.sub(handle, title, count=1)
            break

    if len(title) > 280:
        title = title[:277] + "..."
    return title


# ===========================================================================
# Daily rate guard
# ===========================================================================

DAILY_POST_LIMIT = 40
DAILY_COUNT_PATH = Path("state/x_daily_count.json")


def _check_daily_limit() -> int:
    """Check how many posts remain today. Returns remaining count."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_state = {}

    if DAILY_COUNT_PATH.exists():
        try:
            daily_state = json.loads(DAILY_COUNT_PATH.read_text(encoding="utf-8"))
        except Exception:
            daily_state = {}

    if daily_state.get("date") != today:
        daily_state = {"date": today, "count": 0}

    return DAILY_POST_LIMIT - daily_state.get("count", 0)


def _increment_daily_count(posted: int):
    """Record that we posted N tweets today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_state = {}

    if DAILY_COUNT_PATH.exists():
        try:
            daily_state = json.loads(DAILY_COUNT_PATH.read_text(encoding="utf-8"))
        except Exception:
            daily_state = {}

    if daily_state.get("date") != today:
        daily_state = {"date": today, "count": 0}

    daily_state["count"] = daily_state.get("count", 0) + posted
    DAILY_COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DAILY_COUNT_PATH.write_text(json.dumps(daily_state), encoding="utf-8")


# ===========================================================================
# Core posting logic
# ===========================================================================

def _post_single(draft: dict, api_key: str, api_secret: str,
                 access_token: str, access_secret: str,
                 config: dict,
                 dry_run: bool = False) -> tuple[int, Optional[dict]]:
    """
    Post a single draft to X with OG image.
    Returns (posts_made, tweet_metadata_or_None).
    """
    title = draft.get("title", "").strip()
    link = draft.get("link", "").strip()

    if not title:
        print(f"  ⚠️  Missing title, skipping")
        return (0, None)

    posts_made = 0

    # --- Fetch OG image ---
    media_id = None
    img_bytes = None
    if link:
        img_bytes = _fetch_og_image(link)
        if img_bytes:
            print(f"  🖼️  OG image found ({len(img_bytes) // 1024}KB)")
            if not dry_run:
                media_id = _upload_media(img_bytes, api_key, api_secret, access_token, access_secret)
                if media_id:
                    print(f"  🖼️  Media uploaded: {media_id}")
                else:
                    print(f"  ⚠️  Media upload failed, posting without image")
            else:
                print(f"  🖼️  [DRY-RUN] Would upload image")
        else:
            print(f"  ⚠️  No OG image found")

    # --- Format news-wire tweet (title + @handle) ---
    tweet_text = _format_news_tweet(draft)
    print(f"  📝 Tweet: {tweet_text}")

    # --- Post tweet ---
    tweet_metadata = None
    if not dry_run:
        media_ids = [media_id] if media_id else None
        post_result = _post_to_x(tweet_text, api_key, api_secret, access_token, access_secret,
                                 media_ids=media_ids)
        tweet_id = post_result.get("data", {}).get("id")
        print(f"  ✅ Posted! Tweet ID: {tweet_id}")
        if tweet_id:
            tweet_url = f"https://x.com/i/web/status/{tweet_id}"
            print(f"  🔗 {tweet_url}")
            tweet_metadata = {
                "tweet_id": tweet_id,
                "tweet_text": tweet_text,
                "tweet_url": tweet_url,
            }
        posts_made += 1
    else:
        print(f"  ✅ [DRY-RUN] Would post tweet" + (" with image" if media_id or img_bytes else ""))
        posts_made += 1

    return (posts_made, tweet_metadata)


# ===========================================================================
# Main posting functions
# ===========================================================================

def post_from_drafts(drafts_path: str = "out/alerts_drafts.json",
                     dry_run: bool = False) -> None:
    """
    Post drafts to X immediately.

    - News-wire format tweets (title + @company handle)
    - Fetches OG images and attaches to tweets
    - Respects daily rate limit (40/day)
    """
    config = _load_config()
    alerts_config = config.get("alerts", {})

    if dry_run:
        print("🔧 DRY-RUN MODE: No tweets will be posted\n")

    # Load credentials (not required in dry-run)
    api_key = api_secret = access_token = access_secret = ""
    if not dry_run:
        api_key = _get_env("X_API_KEY")
        api_secret = _get_env("X_API_SECRET")
        access_token = _get_env("X_ACCESS_TOKEN")
        access_secret = _get_env("X_ACCESS_SECRET")

    # Load drafts
    drafts_file = Path(drafts_path)
    if not drafts_file.exists():
        print(f"⚠️  No drafts file found at {drafts_path}")
        return

    drafts = json.loads(drafts_file.read_text(encoding="utf-8"))
    if not drafts:
        print("ℹ️  No drafts to post")
        return

    # Final safety net: load links already posted to X from feed.json
    feed_path = Path("out/feed.json")
    posted_links: set[str] = set()
    feed_data: dict = {"entries": []}
    if feed_path.exists():
        try:
            feed_data = json.loads(feed_path.read_text(encoding="utf-8"))
            for entry in feed_data.get("entries", []):
                if entry.get("posted_to_x") and entry.get("link"):
                    posted_links.add(canonicalize_url(entry["link"].strip()))
        except Exception:
            pass

    # Remove drafts whose links were already posted to X (canonical URL match)
    if posted_links:
        before = len(drafts)
        drafts = [d for d in drafts if canonicalize_url(d.get("link", "").strip()) not in posted_links]
        deduped = before - len(drafts)
        if deduped:
            print(f"⏭️  Skipped {deduped} draft(s) already posted to X (feed.json URL dedup)")

    # Title-similarity guard: catch same story from different URLs
    if drafts:
        try:
            feed_posted_titles = []
            for entry in feed_data.get("entries", []):
                t = entry.get("title", "")
                if t and entry.get("posted_to_x"):
                    feed_posted_titles.append(t)

            if feed_posted_titles:
                title_deduped = []
                for d in drafts:
                    draft_title = d.get("title", "")
                    draft_tokens = tokenize_title(draft_title)
                    draft_entities = extract_entities(draft_title)
                    is_dup = False
                    for ft in feed_posted_titles:
                        ft_tokens = tokenize_title(ft)
                        jac = jaccard_similarity(draft_tokens, ft_tokens)
                        ft_entities = extract_entities(ft)
                        shared = draft_entities & ft_entities
                        # High token overlap OR shared entity with moderate overlap
                        if jac >= 0.50 or (shared and jac >= 0.25):
                            print(
                                f"⏭️  Skipped draft (feed.json title dedup, jac={jac:.2f}"
                                f"{', entity=' + list(shared)[0] if shared else ''}): "
                                f"\"{draft_title[:60]}...\""
                            )
                            is_dup = True
                            break
                    if not is_dup:
                        title_deduped.append(d)

                removed = len(drafts) - len(title_deduped)
                if removed:
                    print(f"⏭️  Skipped {removed} draft(s) already posted to X (feed.json title dedup)")
                drafts = title_deduped
        except Exception as e:
            print(f"⚠️  Feed.json title dedup error ({e}), continuing without it")

    # Filter by ranking agent's post_to_x flag (set during run_alerts.py)
    to_post = [d for d in drafts if d.get("post_to_x", False)]
    print(f"📋 {len(drafts)} total draft(s), {len(to_post)} flagged for X by ranking agent")

    if not to_post:
        print("ℹ️  No drafts to post")
        return

    # Check daily rate limit
    remaining = _check_daily_limit()
    if remaining <= 0:
        print(f"⚠️  X daily limit reached ({DAILY_POST_LIMIT} posts today), skipping")
        return

    if len(to_post) > remaining:
        print(f"⚠️  Limiting to {remaining} posts (daily cap)")
        to_post = to_post[:remaining]

    posted_count = 0
    failed_count = 0
    feed_entries = []

    for idx, draft in enumerate(to_post, 1):
        score = draft.get("score", 0)
        title = draft.get("title", "")[:60]
        print(f"\n{'─' * 60}")
        print(f"[{idx}/{len(to_post)}] score={score} | {title}...")

        try:
            posts, tweet_meta = _post_single(
                draft, api_key, api_secret, access_token, access_secret,
                config, dry_run=dry_run,
            )
            posted_count += posts

            if tweet_meta and not dry_run:
                now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                feed_entries.append({
                    "id": draft.get("id", ""),
                    "title": draft.get("title", ""),
                    "link": draft.get("link", ""),
                    "snippet": draft.get("snippet", ""),
                    "score": draft.get("score", 0),
                    "matched_topics": draft.get("matched_topics", []),
                    "ai_category": draft.get("ai_category", ""),
                    "ai_priority": draft.get("ai_priority", ""),
                    "posted_at": now_iso,
                    "source": draft.get("source", ""),
                    "feed_name": draft.get("feed_name", ""),
                    "published_at": draft.get("published_at", ""),
                    "posted_to_telegram": True,
                    "posted_to_x": True,
                    "tweet_id": tweet_meta.get("tweet_id"),
                    "tweet_text": tweet_meta.get("tweet_text"),
                    "tweet_url": tweet_meta.get("tweet_url"),
                })

                # Post AI trade analysis as a reply thread (if enabled)
                if alerts_config.get("trade_analysis_x", False):
                    tid = tweet_meta.get("tweet_id")
                    article_link = draft.get("link", "")
                    if tid and article_link:
                        _post_analysis_reply(
                            tid, article_link,
                            api_key, api_secret, access_token, access_secret,
                            dry_run=dry_run,
                        )
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed_count += 1

    # Write feed entries (upserts onto any TG-only entries from earlier step)
    if feed_entries:
        write_entries_to_feed(feed_entries)

    # Save state
    if posted_count > 0 and not dry_run:
        _increment_daily_count(posted_count)

    print(f"\n{'═' * 60}")
    print(f"📊 X Summary: {posted_count} posted, {failed_count} failed")
    remaining_after = _check_daily_limit()
    print(f"📊 Daily budget remaining: {remaining_after}/{DAILY_POST_LIMIT}")


def extract_html_from_issue_body(issue_body: str) -> tuple[Optional[str], Optional[str]]:
    """Extract title and link from GitHub issue body containing Telegram HTML."""
    if not issue_body:
        return None, None

    m = re.search(r"```html\s*(.*?)\s*```", issue_body, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return None, None

    html_content = m.group(1).strip()

    title_match = re.search(r"<b>(.*?)</b>", html_content, flags=re.DOTALL)
    if not title_match:
        return None, None

    title = title_match.group(1).strip()
    title = title.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    link_match = re.search(r'<a\s+href=["\']([^"\']+)["\']', html_content)
    if not link_match:
        return None, None

    link = link_match.group(1).strip()
    link = link.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    return title, link


def post_from_issue_body(issue_body_path: str) -> None:
    """Read GitHub issue body from file, extract content, and post to X."""
    api_key = _get_env("X_API_KEY")
    api_secret = _get_env("X_API_SECRET")
    access_token = _get_env("X_ACCESS_TOKEN")
    access_secret = _get_env("X_ACCESS_SECRET")

    issue_body = Path(issue_body_path).read_text(encoding="utf-8")
    print(f"📄 Read issue body from {issue_body_path} ({len(issue_body)} chars)")

    title, link = extract_html_from_issue_body(issue_body)
    if not title or not link:
        print(f"⚠️  Issue body preview (first 500 chars):\n{issue_body[:500]}")
        raise RuntimeError("Could not extract title and link from issue body")

    print(f"📝 Title: {title}")
    print(f"🔗 Link: {link}")

    tweet_text = _format_news_tweet({"title": title})
    print(f"🐦 Tweet ({len(tweet_text)} chars): {tweet_text}")

    result = _post_to_x(tweet_text, api_key, api_secret, access_token, access_secret)
    tweet_id = result.get("data", {}).get("id")

    print(f"✅ Posted to X! Tweet ID: {tweet_id}")
    if tweet_id:
        print(f"🔗 View at: https://x.com/i/web/status/{tweet_id}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Post alerts to X (Twitter)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Post from GitHub issue body (used in approval workflow)
  python scripts/publish_x.py --from-issue-file /tmp/issue_body.txt

  # Post all drafts (used in auto-approve mode)
  python scripts/publish_x.py --from-drafts

  # Dry-run: see what would be posted without actually posting
  python scripts/publish_x.py --from-drafts --dry-run

Environment Variables Required:
  X_API_KEY         - Twitter API Key (Consumer Key)
  X_API_SECRET      - Twitter API Secret (Consumer Secret)
  X_ACCESS_TOKEN    - Twitter Access Token
  X_ACCESS_SECRET   - Twitter Access Token Secret
        """
    )

    parser.add_argument(
        "--from-issue-file", type=str,
        help="Path to file containing GitHub issue body with Telegram HTML"
    )
    parser.add_argument(
        "--from-drafts", action="store_true",
        help="Post filtered drafts to X (auto-approve mode)"
    )
    parser.add_argument(
        "--drafts-path", type=str, default="out/alerts_drafts.json",
        help="Path to drafts file (default: out/alerts_drafts.json)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be posted without actually posting to X"
    )

    args = parser.parse_args()

    if args.from_issue_file:
        post_from_issue_body(args.from_issue_file)
    elif args.from_drafts:
        post_from_drafts(args.drafts_path, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
