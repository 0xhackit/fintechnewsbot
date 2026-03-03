#!/usr/bin/env python3
"""
Post approved alerts to X (Twitter) using the v2 API.

Features:
  - Tiered posting: score >= 80 posts immediately + thread; 60-79 queued for peak hours
  - AI-enhanced tweets: Claude Haiku with 6 rotating styles, @handles, no links
  - OG image fetching: attaches article images for higher engagement
  - Peak-hour scheduling: queues mid-tier articles for configured time windows
  - Style rotation: tracks recent styles to ensure variety
  - Fail-open: falls back to plain title if AI is unavailable
  - Daily rate guard: caps posts at 40/day (free tier = 50/day)
  - Dry-run mode: test everything without posting
"""
import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin
import requests

# Ensure repo root is on sys.path so we can import feed_writer and src modules
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from feed_writer import write_entries_to_feed
from src.ai_filter import should_post_to_x


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

ALL_STYLES = [
    "TRADFI_BRIDGE", "EXPLAINER", "IMPACT",
    "QUESTION", "STAT_LED", "CONTRARIAN",
]


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

def _format_tweet(title: str, max_length: int = 280) -> str:
    """Fallback: format a plain tweet with just the title (no link)."""
    title = title.strip()
    if len(title) > max_length:
        title = title[:max_length - 3] + "..."
    return title


PRIORITY_GUIDANCE = {
    "high": (
        "This is a HIGH-PRIORITY story. Use an urgent, authoritative hook. "
        "You may prefix with BREAKING: if appropriate.\n"
        "Write a TWO-PART tweet:\n"
        "- Line 1: A concise, punchy hook (1 sentence)\n"
        "- Line 2 (after a blank line): One short sentence — why it matters, TradFi context, or what to watch next\n"
        "CRITICAL: Both parts combined MUST be under 270 characters total. Keep each part SHORT."
    ),
    "medium": (
        "This is a MEDIUM-PRIORITY story. Use an insightful, analytical hook. "
        "Do NOT use BREAKING: prefix."
    ),
    "low": (
        "This is a LOW-PRIORITY but relevant story. Use an educational or explanatory hook. "
        "Do NOT use BREAKING: prefix."
    ),
}


def _generate_ai_tweet(draft: dict, avoid_styles: list[str] = None) -> Optional[tuple[str, str]]:
    """
    Generate an AI-enhanced tweet using Claude Haiku.

    No article link in tweet. Uses @handles, 6 rotating styles.
    Returns (tweet_text, style_used) tuple, or None on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    title = draft.get("title", "")
    snippet = draft.get("snippet", "")
    matched_topics = draft.get("matched_topics", [])
    ai_priority = draft.get("ai_priority", "medium") or "medium"

    # Build @handles hint from title
    title_lower = title.lower()
    relevant_handles = []
    for company, handle in COMPANY_HANDLES.items():
        if company in title_lower and handle not in relevant_handles:
            relevant_handles.append(handle)

    handles_hint = ""
    if relevant_handles:
        handles_hint = f"\nRelevant company @handles you SHOULD use: {', '.join(relevant_handles[:3])}"

    avoid_hint = ""
    if avoid_styles:
        avoid_hint = f"\nIMPORTANT: Do NOT use these styles (recently used): {', '.join(avoid_styles)}"

    guidance = PRIORITY_GUIDANCE.get(ai_priority, PRIORITY_GUIDANCE["medium"])

    prompt = f"""You are a fintech news editor writing a tweet for a professional audience.

Given this article:
TITLE: {title}
SNIPPET: {snippet[:300] if snippet else '(none)'}
TOPICS: {', '.join(matched_topics) if matched_topics else 'general fintech'}

{guidance}

Write a single tweet using EXACTLY ONE of these styles:
- TRADFI_BRIDGE: Connect this news to a traditional finance concept
- EXPLAINER: Briefly explain the tech/product for someone outside crypto
- IMPACT: State the concrete implication for the industry
- QUESTION: Open with a compelling rhetorical question
- STAT_LED: Lead with a number or statistic from the article
- CONTRARIAN: Offer a "most people miss this" angle
{avoid_hint}

Rules:
1. Use company @handles where natural{handles_hint}
2. Do NOT include any article link or URL
3. NO hashtags. NO emojis. Professional, factual tone.
4. TOTAL tweet MUST be under 270 characters (count carefully)
5. On the LAST line of your response, write: STYLE_USED: <style_name>

Return the tweet text followed by the STYLE_USED line. Nothing else."""

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Parse STYLE_USED from last line
        style_used = "UNKNOWN"
        lines = raw.split("\n")
        tweet_lines = []
        for line in lines:
            if line.strip().upper().startswith("STYLE_USED:"):
                style_used = line.split(":", 1)[1].strip().upper().replace(" ", "_")
                if style_used not in ALL_STYLES:
                    style_used = "UNKNOWN"
            else:
                tweet_lines.append(line)

        tweet = "\n".join(tweet_lines).strip()

        # Strip quotes the model may wrap it in
        if tweet.startswith('"') and tweet.endswith('"'):
            tweet = tweet[1:-1]
        if tweet.startswith("'") and tweet.endswith("'"):
            tweet = tweet[1:-1]

        # Remove any URLs the model may have added despite instructions
        tweet = re.sub(r'https?://\S+', '', tweet).strip()

        if len(tweet) > 280:
            print(f"  ⚠️  AI tweet too long ({len(tweet)} chars), using fallback")
            return None

        if len(tweet) < 20:
            print(f"  ⚠️  AI tweet too short ({len(tweet)} chars), using fallback")
            return None

        return (tweet, style_used)

    except Exception as e:
        print(f"  ⚠️  AI tweet generation failed ({e}), using fallback")
        return None


# ===========================================================================
# Style rotation
# ===========================================================================

STYLE_ROTATION_PATH = Path("state/x_style_rotation.json")
STYLE_HISTORY_SIZE = 4


def _load_style_history() -> list[str]:
    """Load the last N styles used from state file."""
    if not STYLE_ROTATION_PATH.exists():
        return []
    try:
        data = json.loads(STYLE_ROTATION_PATH.read_text(encoding="utf-8"))
        return data.get("recent_styles", [])[-STYLE_HISTORY_SIZE:]
    except Exception:
        return []


def _save_style_history(styles: list[str]):
    """Save updated style history."""
    STYLE_ROTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    trimmed = styles[-STYLE_HISTORY_SIZE:]
    STYLE_ROTATION_PATH.write_text(
        json.dumps({"recent_styles": trimmed}, indent=2),
        encoding="utf-8"
    )


# ===========================================================================
# Peak-hour scheduling
# ===========================================================================

X_QUEUE_PATH = Path("state/x_queue.json")
X_QUEUE_MAX_SIZE = 50
QUEUE_EXPIRY_HOURS = 24


def _is_peak_hour(config: dict) -> bool:
    """
    Check if current UTC time falls within any configured peak window.
    If no peak_hours_utc configured, ALL hours are peak (backward-compatible).
    """
    peak_windows = config.get("alerts", {}).get("peak_hours_utc", [])
    if not peak_windows:
        return True

    now = datetime.now(timezone.utc)
    current_minutes = now.hour * 60 + now.minute

    for window in peak_windows:
        try:
            start_str, end_str = window.split("-")
            start_h, start_m = map(int, start_str.strip().split(":"))
            end_h, end_m = map(int, end_str.strip().split(":"))
            start_total = start_h * 60 + start_m
            end_total = end_h * 60 + end_m

            if start_total <= end_total:
                if start_total <= current_minutes < end_total:
                    return True
            else:
                # Wraps midnight
                if current_minutes >= start_total or current_minutes < end_total:
                    return True
        except (ValueError, AttributeError):
            continue

    return False


def _load_queue() -> list[dict]:
    """Load the X posting queue."""
    if not X_QUEUE_PATH.exists():
        return []
    try:
        return json.loads(X_QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_queue(queue: list[dict]):
    """Save the X posting queue, capping at max size."""
    if len(queue) > X_QUEUE_MAX_SIZE:
        dropped = len(queue) - X_QUEUE_MAX_SIZE
        queue = queue[-X_QUEUE_MAX_SIZE:]
        print(f"  ⚠️  Queue overflow: dropped {dropped} oldest items (cap={X_QUEUE_MAX_SIZE})")
    X_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    X_QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")


def _add_to_queue(drafts: list[dict]):
    """Add drafts to queue for peak-hour posting. Deduplicates by link."""
    queue = _load_queue()
    existing_links = {item.get("link") for item in queue}
    now_iso = datetime.now(timezone.utc).isoformat()
    new_items = []
    for d in drafts:
        if d.get("link") not in existing_links:
            d["queued_at"] = now_iso
            new_items.append(d)
    queue.extend(new_items)
    _save_queue(queue)
    if new_items:
        print(f"  📥 Queued {len(new_items)} mid-tier draft(s) for peak-hour posting ({len(queue)} total)")


def _drain_queue(new_drafts: list[dict]) -> list[dict]:
    """
    Merge queued items with new drafts, removing expired items.
    Returns combined list sorted by score descending, deduped by link.
    """
    queue = _load_queue()

    # Remove expired items (> 24h old)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=QUEUE_EXPIRY_HOURS)
    valid_queue = []
    expired = 0
    for item in queue:
        queued_at = item.get("queued_at", "")
        try:
            if datetime.fromisoformat(queued_at) >= cutoff:
                valid_queue.append(item)
            else:
                expired += 1
        except (ValueError, TypeError):
            valid_queue.append(item)  # Keep items without timestamp

    if expired:
        print(f"  🗑️  Dropped {expired} expired queued item(s) (> {QUEUE_EXPIRY_HOURS}h old)")

    # Merge with new drafts, dedup by link
    seen_links = set()
    combined = []
    for item in valid_queue + new_drafts:
        link = item.get("link", "")
        if link and link not in seen_links:
            seen_links.add(link)
            combined.append(item)

    # Sort by score descending
    combined.sort(key=lambda d: d.get("score", 0), reverse=True)

    # Clear the queue (it's been drained)
    _save_queue([])

    return combined


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
                 style_history: list[str], config: dict,
                 dry_run: bool = False) -> tuple[int, list[str], Optional[dict]]:
    """
    Post a single draft to X with AI generation and image.
    High-priority tweets get a two-part format (hook + insight) in one tweet.
    Returns (posts_made, updated_style_history, tweet_metadata_or_None).
    """
    title = draft.get("title", "").strip()
    link = draft.get("link", "").strip()

    if not title:
        print(f"  ⚠️  Missing title, skipping")
        return (0, style_history, None)

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

    # --- Generate tweet ---
    avoid_styles = list(set(style_history[-STYLE_HISTORY_SIZE:])) if style_history else []
    if len(avoid_styles) >= len(ALL_STYLES) - 1:
        avoid_styles = avoid_styles[-2:]

    result = _generate_ai_tweet(draft, avoid_styles=avoid_styles)
    if result:
        tweet_text, style_used = result
        style_history.append(style_used)
        print(f"  🤖 AI tweet (style={style_used}):")
    else:
        tweet_text = _format_tweet(title)
        print(f"  📝 Fallback tweet:")

    print(f"     {tweet_text}")

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

    return (posts_made, style_history, tweet_metadata)


# ===========================================================================
# Main posting functions
# ===========================================================================

def post_from_drafts(drafts_path: str = "out/alerts_drafts.json",
                     dry_run: bool = False) -> None:
    """
    Post filtered, AI-enhanced drafts to X.

    - Tiered posting: score >= 80 immediate + thread, 60-79 peak-hour queue
    - Generates AI tweets with Claude Haiku (falls back to title only)
    - Fetches OG images and attaches to tweets
    - Respects daily rate limit (40/day)
    """
    config = _load_config()
    alerts_config = config.get("alerts", {})
    min_score_for_x = alerts_config.get("min_score_for_x", 45)
    thread_threshold = alerts_config.get("thread_score_threshold", 80)

    # AI quality gate thresholds: articles between these scores get an AI review
    AI_GATE_HIGH = 75  # Above this: auto-post (no AI check needed)

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
    if feed_path.exists():
        try:
            feed_data = json.loads(feed_path.read_text(encoding="utf-8"))
            for entry in feed_data.get("entries", []):
                if entry.get("posted_to_x") and entry.get("link"):
                    posted_links.add(entry["link"].strip())
        except Exception:
            pass

    # Remove drafts whose links were already posted to X
    if posted_links:
        before = len(drafts)
        drafts = [d for d in drafts if d.get("link", "").strip() not in posted_links]
        deduped = before - len(drafts)
        if deduped:
            print(f"⏭️  Skipped {deduped} draft(s) already posted to X (feed.json dedup)")

    # Filter by X threshold
    x_drafts = [d for d in drafts if d.get("score", 0) >= min_score_for_x]
    print(f"📋 {len(drafts)} total draft(s), {len(x_drafts)} qualify for X (score >= {min_score_for_x})")

    # AI quality gate: articles scoring <= AI_GATE_HIGH get reviewed by Claude Haiku
    if x_drafts and not dry_run:
        gate_filtered = []
        for d in x_drafts:
            s = d.get("score", 0)
            if s > AI_GATE_HIGH:
                gate_filtered.append(d)  # High scorers auto-post
            else:
                # Borderline: ask AI
                post_it, reason = should_post_to_x(
                    d.get("title", ""), d.get("snippet", ""), s
                )
                title_short = d.get("title", "")[:50]
                if post_it:
                    gate_filtered.append(d)
                    print(f"  ✅ AI gate APPROVED (score={s}): {title_short}... — {reason}")
                else:
                    print(f"  🚫 AI gate REJECTED (score={s}): {title_short}... — {reason}")
        rejected = len(x_drafts) - len(gate_filtered)
        if rejected:
            print(f"🤖 AI gate: {len(gate_filtered)} approved, {rejected} rejected")
        x_drafts = gate_filtered

    # Split into urgent (immediate) and mid-tier (peak-hour queue)
    urgent = [d for d in x_drafts if d.get("score", 0) >= thread_threshold]
    mid_tier = [d for d in x_drafts if min_score_for_x <= d.get("score", 0) < thread_threshold]

    peak = _is_peak_hour(config)
    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
    print(f"⏰ Current time: {now_str} ({'PEAK' if peak else 'off-peak'})")

    if urgent:
        print(f"🚨 {len(urgent)} urgent draft(s) (score >= {thread_threshold}) — posting immediately")
    if mid_tier:
        if peak:
            print(f"📊 {len(mid_tier)} mid-tier draft(s) — posting (peak hour)")
        else:
            print(f"📊 {len(mid_tier)} mid-tier draft(s) — queuing for peak hours")

    # Determine what to post now
    to_post = []

    if peak:
        # Peak hour: drain queue + post all new X-eligible drafts
        to_post = _drain_queue(x_drafts)
        queue_count = len(to_post) - len(x_drafts)
        if queue_count > 0:
            print(f"📤 Draining {queue_count} queued item(s) + {len(x_drafts)} new")
    else:
        # Off-peak: post urgent immediately, queue mid-tier
        to_post = urgent
        if mid_tier:
            _add_to_queue(mid_tier)

    if not to_post:
        if not mid_tier:
            print("ℹ️  No drafts to post or queue")
        return

    # Check daily rate limit
    remaining = _check_daily_limit()
    if remaining <= 0:
        print(f"⚠️  X daily limit reached ({DAILY_POST_LIMIT} posts today), skipping")
        if to_post and not peak:
            _add_to_queue(to_post)
        return

    if len(to_post) > remaining:
        print(f"⚠️  Limiting to {remaining} posts (daily cap)")
        # Re-queue excess items
        overflow = to_post[remaining:]
        to_post = to_post[:remaining]
        _add_to_queue(overflow)

    # Load style history
    style_history = _load_style_history()
    posted_count = 0
    failed_count = 0
    feed_entries = []

    for idx, draft in enumerate(to_post, 1):
        score = draft.get("score", 0)
        title = draft.get("title", "")[:60]
        print(f"\n{'─' * 60}")
        print(f"[{idx}/{len(to_post)}] score={score} | {title}...")

        try:
            posts, style_history, tweet_meta = _post_single(
                draft, api_key, api_secret, access_token, access_secret,
                style_history, config, dry_run=dry_run,
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
    _save_style_history(style_history)
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

    tweet_text = _format_tweet(title)
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
  ANTHROPIC_API_KEY - (Optional) For AI-enhanced tweet formatting
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
