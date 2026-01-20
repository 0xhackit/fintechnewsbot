#!/usr/bin/env python3
"""
Post approved alerts to X (Twitter) using the v2 API.
Supports both review-based and auto-approve workflows.
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import Optional
import requests


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


def _post_to_x(text: str, api_key: str, api_secret: str, access_token: str, access_secret: str) -> dict:
    """
    Post a tweet using Twitter API v2 with OAuth 1.0a User Context.

    Args:
        text: Tweet content (max 280 characters)
        api_key: Twitter API Key (Consumer Key)
        api_secret: Twitter API Secret (Consumer Secret)
        access_token: Twitter Access Token
        access_secret: Twitter Access Token Secret

    Returns:
        Response JSON from Twitter API
    """
    try:
        from requests_oauthlib import OAuth1
    except ImportError:
        raise RuntimeError(
            "requests-oauthlib is required for X posting. "
            "Install with: pip install requests-oauthlib"
        )

    url = "https://api.twitter.com/2/tweets"

    # OAuth 1.0a authentication
    auth = OAuth1(
        api_key,
        api_secret,
        access_token,
        access_secret,
    )

    payload = {"text": text}

    response = requests.post(
        url,
        auth=auth,
        json=payload,
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 402:
        raise RuntimeError(
            f"X API Credits Depleted Error\n\n"
            f"Your X API account has no credits. This usually means:\n"
            f"1. You're not properly enrolled in the Free Tier, OR\n"
            f"2. You've exceeded the Free Tier limits (50 posts/day)\n\n"
            f"Fix this by:\n"
            f"1. Go to https://developer.twitter.com/en/portal/dashboard\n"
            f"2. Check your account status and tier enrollment\n"
            f"3. Ensure you're on the FREE TIER (not trial or other)\n"
            f"4. If on Free Tier, wait until midnight UTC for credits to reset\n"
            f"5. Monitor your daily usage to stay under 50 posts/day\n\n"
            f"Free Tier limits: 1,500 posts/month (50/day)\n"
            f"Consider using auto_approve: false for better control\n\n"
            f"Original error: {response.text}"
        )

    if response.status_code == 403:
        error_detail = response.json().get('detail', response.text)
        if 'oauth1-permissions' in error_detail.lower():
            raise RuntimeError(
                f"X API Permission Error: Your app needs OAuth 1.0a permissions.\n"
                f"Fix this by:\n"
                f"1. Go to https://developer.twitter.com/en/portal/projects-and-apps\n"
                f"2. Select your app → Settings → User authentication settings\n"
                f"3. Click 'Set up' or 'Edit'\n"
                f"4. Enable 'OAuth 1.0a' with 'Read and Write' permissions\n"
                f"5. Save and regenerate your Access Token & Secret\n"
                f"6. Update GitHub secrets with the NEW tokens\n"
                f"\nOriginal error: {response.text}"
            )
        raise RuntimeError(f"X API error 403: {response.text}")

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"X API error {response.status_code}: {response.text}"
        )

    return response.json()


def _format_tweet(title: str, link: str, max_length: int = 280) -> str:
    """
    Format a tweet with title and link.
    Twitter auto-shortens links to ~23 chars (t.co links).

    Args:
        title: Article title
        link: Article URL
        max_length: Maximum tweet length (default 280)

    Returns:
        Formatted tweet text
    """
    # Twitter shortens all links to ~23 chars
    LINK_LENGTH = 23

    # Calculate available space for title
    # Format: "{title} {link}"
    available_for_title = max_length - LINK_LENGTH - 1  # -1 for space

    title = title.strip()

    # Truncate title if needed
    if len(title) > available_for_title:
        title = title[:available_for_title - 3] + "..."

    return f"{title} {link}"


def extract_html_from_issue_body(issue_body: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract title and link from GitHub issue body containing Telegram HTML.

    Expected format:
    ```html
    <b>Title Here</b> <a href="https://...">LINK</a>
    ```

    Returns:
        Tuple of (title, link) or (None, None) if not found
    """
    if not issue_body:
        return None, None

    # Extract HTML block
    m = re.search(r"```html\s*(.*?)\s*```", issue_body, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return None, None

    html_content = m.group(1).strip()

    # Parse title from <b>...</b>
    title_match = re.search(r"<b>(.*?)</b>", html_content, flags=re.DOTALL)
    if not title_match:
        return None, None

    title = title_match.group(1).strip()
    # Decode HTML entities
    title = title.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    # Parse link from <a href="...">
    link_match = re.search(r'<a\s+href=["\']([^"\']+)["\']', html_content)
    if not link_match:
        return None, None

    link = link_match.group(1).strip()
    link = link.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    return title, link


def post_from_issue_body(issue_body_path: str) -> None:
    """
    Read GitHub issue body from file, extract content, and post to X.

    Args:
        issue_body_path: Path to file containing the GitHub issue body
    """
    # Load credentials
    api_key = _get_env("X_API_KEY")
    api_secret = _get_env("X_API_SECRET")
    access_token = _get_env("X_ACCESS_TOKEN")
    access_secret = _get_env("X_ACCESS_SECRET")

    # Read issue body
    issue_body = Path(issue_body_path).read_text(encoding="utf-8")
    print(f"📄 Read issue body from {issue_body_path} ({len(issue_body)} chars)")

    # Extract content
    title, link = extract_html_from_issue_body(issue_body)
    if not title or not link:
        print(f"⚠️  Issue body preview (first 500 chars):\n{issue_body[:500]}")
        raise RuntimeError("Could not extract title and link from issue body")

    print(f"📝 Title: {title}")
    print(f"🔗 Link: {link}")

    # Format tweet
    tweet_text = _format_tweet(title, link)
    print(f"🐦 Tweet ({len(tweet_text)} chars): {tweet_text}")

    # Post to X
    result = _post_to_x(tweet_text, api_key, api_secret, access_token, access_secret)
    tweet_id = result.get("data", {}).get("id")

    print(f"✅ Posted to X! Tweet ID: {tweet_id}")
    if tweet_id:
        print(f"🔗 View at: https://x.com/i/web/status/{tweet_id}")


def post_from_drafts(drafts_path: str = "out/alerts_drafts.json") -> None:
    """
    Post all drafts from alerts_drafts.json to X.
    Used in auto-approve mode.

    Args:
        drafts_path: Path to alerts_drafts.json file
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

    print(f"📋 Found {len(drafts)} draft(s) to post to X")

    posted_count = 0
    failed_count = 0

    for idx, draft in enumerate(drafts, 1):
        title = draft.get("title", "").strip()
        link = draft.get("link", "").strip()

        if not title or not link:
            print(f"⚠️  Draft {idx}: Missing title or link, skipping")
            failed_count += 1
            continue

        try:
            tweet_text = _format_tweet(title, link)
            print(f"\n🐦 [{idx}/{len(drafts)}] Posting: {tweet_text[:80]}...")

            result = _post_to_x(tweet_text, api_key, api_secret, access_token, access_secret)
            tweet_id = result.get("data", {}).get("id")

            print(f"✅ Posted! Tweet ID: {tweet_id}")
            posted_count += 1

        except Exception as e:
            print(f"❌ Failed to post draft {idx}: {e}")
            failed_count += 1

    print(f"\n📊 Summary: {posted_count} posted, {failed_count} failed")


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
        """
    )

    parser.add_argument(
        "--from-issue-file",
        type=str,
        help="Path to file containing GitHub issue body with Telegram HTML"
    )
    parser.add_argument(
        "--from-drafts",
        action="store_true",
        help="Post all drafts from alerts_drafts.json (auto-approve mode)"
    )
    parser.add_argument(
        "--drafts-path",
        type=str,
        default="out/alerts_drafts.json",
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
