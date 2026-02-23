#!/usr/bin/env python3
"""
Post approved alerts to X (Twitter) using the v2 API.

Features:
  - Score-based filtering: only post articles above min_score_for_x threshold
  - AI-enhanced tweets: Claude Haiku generates BREAKING/LATEST hooks with @handles
  - Fail-open: falls back to plain title+link if AI is unavailable
  - Daily rate guard: caps posts at 40/day (free tier = 50/day)
"""
import os
import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import requests


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
# Environment + auth helpers
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


# ===========================================================================
# Twitter API v2 posting
# ===========================================================================

def _post_to_x(text: str, api_key: str, api_secret: str, access_token: str, access_secret: str) -> dict:
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
# Tweet formatting
# ===========================================================================

def _format_tweet(title: str, link: str, max_length: int = 280) -> str:
    """Fallback: format a plain tweet with title and link."""
    LINK_LENGTH = 23  # Twitter t.co shortening
    available_for_title = max_length - LINK_LENGTH - 1
    title = title.strip()
    if len(title) > available_for_title:
        title = title[:available_for_title - 3] + "..."
    return f"{title} {link}"


def _generate_ai_tweet(title: str, link: str, snippet: str = "", score: int = 0) -> Optional[str]:
    """
    Generate an AI-enhanced tweet using Claude Haiku.

    Format: BREAKING/LATEST + hook + @handles + link. No hashtags.
    Rotates between 3 styles: TradFi bridge, explainer, impact.

    Returns formatted tweet string, or None on failure (caller falls back).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    # Build @handles hint from title
    title_lower = title.lower()
    relevant_handles = []
    for company, handle in COMPANY_HANDLES.items():
        if company in title_lower and handle not in relevant_handles:
            relevant_handles.append(handle)

    handles_hint = ""
    if relevant_handles:
        handles_hint = f"\nRelevant company @handles you SHOULD use: {', '.join(relevant_handles[:3])}"

    prompt = f"""You are a fintech news editor writing a tweet for a professional audience.

Given this article:
TITLE: {title}
SNIPPET: {snippet[:300] if snippet else '(none)'}

Write a single tweet following these STRICT rules:

1. Start with BREAKING: or LATEST: (use BREAKING for major launches, regulatory actions, large deals; LATEST for everything else)
2. Write 1-2 sentences using ONE of these styles (rotate, don't always pick the same):
   - TRADFI BRIDGE: Connect this news to a traditional finance concept (e.g., how this replaces T+2 settlement, how this compares to existing banking rails)
   - EXPLAINER: Briefly explain what the tech/product does for someone outside crypto (e.g., "Tokenized deposits work like digital bank deposits but settle in seconds")
   - IMPACT: State the concrete implication for the industry (e.g., "This puts traditional fixed income on public rails for the first time")
3. Include the article link exactly as: {link}
4. Use company @handles where they fit naturally in the sentence{handles_hint}
5. NO hashtags. NO emojis.
6. Professional, factual tone. Not clickbait.
7. TOTAL tweet MUST be under 250 characters (this is critical — count carefully)

Return ONLY the tweet text. Nothing else."""

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        tweet = message.content[0].text.strip()

        # Strip any quotes the model may wrap it in
        if tweet.startswith('"') and tweet.endswith('"'):
            tweet = tweet[1:-1]
        if tweet.startswith("'") and tweet.endswith("'"):
            tweet = tweet[1:-1]

        # Ensure link is present
        if link not in tweet:
            tweet = f"{tweet} {link}"

        # Validate length (t.co counts links as 23 chars)
        effective_length = len(tweet.replace(link, "X" * 23))
        if effective_length > 280:
            print(f"  ⚠️  AI tweet too long ({effective_length} chars), using fallback")
            return None

        return tweet

    except Exception as e:
        print(f"  ⚠️  AI tweet generation failed ({e}), using fallback")
        return None


# ===========================================================================
# Daily rate guard
# ===========================================================================

DAILY_POST_LIMIT = 40  # Free tier = 50/day, leave headroom
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
# Main posting functions
# ===========================================================================

def post_from_drafts(drafts_path: str = "out/alerts_drafts.json") -> None:
    """
    Post filtered, AI-enhanced drafts to X.

    - Filters by min_score_for_x from config.json
    - Generates AI tweets with Claude Haiku (falls back to title+link)
    - Respects daily rate limit (40/day)
    """
    # Load credentials
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

    # Load X score threshold from config
    config_path = Path("config.json")
    min_score_for_x = 60  # default
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            min_score_for_x = config.get("alerts", {}).get("min_score_for_x", 60)
        except Exception:
            pass

    # Filter drafts by X threshold
    x_drafts = [d for d in drafts if d.get("score", 0) >= min_score_for_x]
    print(f"📋 {len(drafts)} total draft(s), {len(x_drafts)} qualify for X (score >= {min_score_for_x})")

    if not x_drafts:
        print("ℹ️  No drafts meet X score threshold")
        return

    # Check daily rate limit
    remaining = _check_daily_limit()
    if remaining <= 0:
        print(f"⚠️  X daily limit reached ({DAILY_POST_LIMIT} posts today), skipping")
        return

    if len(x_drafts) > remaining:
        print(f"⚠️  Limiting to {remaining} posts (daily cap)")
        x_drafts = x_drafts[:remaining]

    posted_count = 0
    failed_count = 0

    for idx, draft in enumerate(x_drafts, 1):
        title = draft.get("title", "").strip()
        link = draft.get("link", "").strip()
        snippet = draft.get("snippet", "")
        score = draft.get("score", 0)

        if not title or not link:
            print(f"⚠️  Draft {idx}: Missing title or link, skipping")
            failed_count += 1
            continue

        try:
            # Try AI-enhanced tweet first
            tweet_text = _generate_ai_tweet(title, link, snippet, score)
            if tweet_text:
                print(f"\n🤖 [{idx}/{len(x_drafts)}] AI tweet (score={score}):")
            else:
                tweet_text = _format_tweet(title, link)
                print(f"\n📝 [{idx}/{len(x_drafts)}] Fallback tweet (score={score}):")

            print(f"   {tweet_text}")

            result = _post_to_x(tweet_text, api_key, api_secret, access_token, access_secret)
            tweet_id = result.get("data", {}).get("id")

            print(f"   ✅ Posted! Tweet ID: {tweet_id}")
            if tweet_id:
                print(f"   🔗 https://x.com/i/web/status/{tweet_id}")
            posted_count += 1

        except Exception as e:
            print(f"   ❌ Failed: {e}")
            failed_count += 1

    # Update daily count
    if posted_count > 0:
        _increment_daily_count(posted_count)

    print(f"\n📊 X Summary: {posted_count} posted, {failed_count} failed")


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

    tweet_text = _format_tweet(title, link)
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

  # Post all drafts from custom path
  python scripts/publish_x.py --from-drafts --drafts-path custom/path.json

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

    args = parser.parse_args()

    if args.from_issue_file:
        post_from_issue_body(args.from_issue_file)
    elif args.from_drafts:
        post_from_drafts(args.drafts_path)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
