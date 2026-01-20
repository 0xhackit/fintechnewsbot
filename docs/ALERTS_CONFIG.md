# Alerts Configuration Guide

This document explains how to configure the alerts system to post to Telegram and X (Twitter), and how to enable/disable the review approval process.

## Configuration Options

The alerts system is configured in `config.json` under the `alerts` section:

```json
{
  "alerts": {
    "auto_approve": false,
    "post_to_telegram": true,
    "post_to_x": true
  }
}
```

### Configuration Fields

- **`auto_approve`** (boolean, default: `false`)
  - When `false`: Alerts require manual approval via GitHub issues before posting
  - When `true`: Alerts are automatically posted without review
  - **Important**: Only set to `true` if you're confident in your filtering criteria

- **`post_to_telegram`** (boolean, default: `true`)
  - When `true`: Posts approved alerts to Telegram
  - When `false`: Skips Telegram posting

- **`post_to_x`** (boolean, default: `true`)
  - When `true`: Posts approved alerts to X (Twitter)
  - When `false`: Skips X posting
  - **Note**: Free Tier allows 50 posts/day (~1,500/month)

## Workflows

### Review-Based Workflow (default)

When `auto_approve: false`:

1. **Alerts Prepare** workflow runs every 5 minutes
   - Fetches news from configured sources
   - Ranks items by relevance
   - Creates GitHub issues for each new alert (titled "APPROVAL: ...")
   - Issues are labeled with `pending`

2. **Manual Review**
   - Review the GitHub issue
   - Add the `approve` label to publish
   - Or add the `reject` label to skip

3. **Publish on Approve** workflow triggers when `approve` label is added
   - Posts to Telegram (if `post_to_telegram: true`)
   - Posts to X (if `post_to_x: true`)
   - Closes the issue with a comment indicating where it was posted

### Auto-Approve Workflow

When `auto_approve: true`:

1. **Auto-Publish Alerts** workflow runs every 5 minutes
   - Fetches news from configured sources
   - Ranks items by relevance
   - Automatically posts all new alerts to configured platforms
   - No GitHub issues are created
   - No manual review required

**⚠️ Warning**: Use auto-approve mode carefully. Ensure your keyword filters and scoring logic are well-tuned to avoid posting irrelevant content.

## Required Secrets

### Telegram Secrets
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `TELEGRAM_CHAT_ID` - Chat/channel ID where messages will be posted

### X (Twitter) Secrets
- `X_API_KEY` - Twitter API Key (Consumer Key)
- `X_API_SECRET` - Twitter API Secret (Consumer Secret)
- `X_ACCESS_TOKEN` - Twitter Access Token
- `X_ACCESS_SECRET` - Twitter Access Token Secret

### Telegram Scraping (optional)
- `TG_API_ID` - Telegram API ID from https://my.telegram.org
- `TG_API_HASH` - Telegram API Hash from https://my.telegram.org

Add these in: **Repository Settings → Secrets and variables → Actions → New repository secret**

## Getting X (Twitter) API Credentials

### X API Free Tier
The Free Tier provides:
- ✅ **1,500 posts per month** (~50 posts per day)
- ✅ Perfect for alerts systems with moderate volume
- ✅ $0 cost

### Setup Steps
1. Apply for a Twitter Developer Account at https://developer.twitter.com
2. Sign up for the **Free Tier** (no payment required)
3. Create a new app in the Developer Portal
4. Go to **Settings → User authentication settings** → Click **"Set up"**
5. **Enable OAuth 1.0a** checkbox
6. Set **App permissions** to **"Read and Write"**
7. Add required URLs (Callback: `http://localhost`, Website: your site/repo)
8. **Save** the settings
9. Go to **Keys and Tokens** tab
10. **Regenerate Access Token & Secret** (CRITICAL: must regenerate after enabling OAuth 1.0a!)
11. Copy all 4 credentials:
    - API Key (Consumer Key)
    - API Secret (Consumer Secret)
    - Access Token
    - Access Token Secret
12. Add all four credentials as GitHub secrets

⚠️ **Common Mistake**: If you get a 403 error about "oauth1-permissions", you forgot to:
- Enable OAuth 1.0a in User authentication settings, OR
- Regenerate your Access Token & Secret after enabling it

### Rate Limit Management
With the Free Tier limit of 50 posts/day:
- **Manual Review Mode**: Each approved alert posts once - no issues
- **Auto-Approve Mode**: Limit alerts to ~2 per hour max
  - Adjust scoring thresholds in config.json
  - Consider using `auto_approve: false` for better control
  - Monitor daily post count to stay under 50/day

## Tweet Format

Tweets are formatted as:
```
{title} {link}
```

- Titles are automatically truncated to fit Twitter's 280 character limit
- Links are auto-shortened by Twitter to ~23 characters (t.co)
- Maximum title length: ~254 characters

## Examples

### Example 1: Both Platforms, Manual Review (Default)
```json
{
  "alerts": {
    "auto_approve": false,
    "post_to_telegram": true,
    "post_to_x": true
  }
}
```

Result: Alerts require GitHub issue approval, then post to both Telegram and X.

### Example 2: Auto-Approve, Both Platforms
```json
{
  "alerts": {
    "auto_approve": true,
    "post_to_telegram": true,
    "post_to_x": true
  }
}
```

Result: All new alerts automatically post to both platforms without review.

### Example 3: Telegram Only, Manual Review
```json
{
  "alerts": {
    "auto_approve": false,
    "post_to_telegram": true,
    "post_to_x": false
  }
}
```

Result: Alerts require GitHub issue approval, then post only to Telegram.

### Example 4: X Only, Auto-Approve
```json
{
  "alerts": {
    "auto_approve": true,
    "post_to_telegram": false,
    "post_to_x": true
  }
}
```

Result: All new alerts automatically post only to X without review.

## Testing

### Test X Posting (Manual)
```bash
# Export your credentials
export X_API_KEY="your_api_key"
export X_API_SECRET="your_api_secret"
export X_ACCESS_TOKEN="your_access_token"
export X_ACCESS_SECRET="your_access_secret"

# Test posting a single alert
echo '**Headline:** Test Article
**Link:** https://example.com

**Telegram draft (HTML):**

```html
<b>Test Article</b> <a href="https://example.com">LINK</a>
```' > /tmp/test_issue.txt

python scripts/publish_x.py --from-issue-file /tmp/test_issue.txt
```

### Test Telegram Posting (Manual)
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

python scripts/publish_telegram.py --from-issue-file /tmp/test_issue.txt
```

## Troubleshooting

### X API Errors

**Error: 401 Unauthorized**
- Check that all four credentials are correct
- Ensure your app has "Read and Write" permissions
- Regenerate Access Token & Secret if you changed permissions

**Error: 403 Forbidden - "oauth1-permissions"**
This is the most common error! It means OAuth 1.0a is not properly configured.

**Fix:**
1. Go to https://developer.twitter.com/en/portal/projects-and-apps
2. Select your app → **Settings** → **User authentication settings**
3. Click **"Edit"**
4. Ensure **OAuth 1.0a** checkbox is ENABLED
5. Set **App permissions** to **"Read and Write"**
6. Click **"Save"**
7. Go to **"Keys and Tokens"** tab
8. Click **"Regenerate"** on Access Token & Secret
9. Update GitHub secrets with the NEW Access Token & Secret

**Important**: Old tokens won't work after enabling OAuth 1.0a - you MUST regenerate!

**Error: 403 Forbidden - Other reasons**
- Your app may not have elevated access
- Check Twitter Developer Portal for any restrictions
- Ensure your developer account is in good standing

**Error: 429 Rate Limit**
- Free Tier: 50 posts per day (1,500/month)
- If you hit the limit, you've posted 50 times today
- Posts reset at midnight UTC
- Solutions:
  - Use `auto_approve: false` for better control
  - Increase scoring thresholds to reduce alert volume
  - Temporarily disable X: set `post_to_x: false`

### Telegram Errors

**Error: Unauthorized**
- Check `TELEGRAM_BOT_TOKEN` is correct
- Ensure the bot has been added to the chat/channel

**Error: Chat not found**
- Check `TELEGRAM_CHAT_ID` is correct
- For channels, ID should be like `-1001234567890`
- For private chats, use numeric user ID

## Workflow Files

- `.github/workflows/alerts_prepare.yml` - Creates approval issues (review mode)
- `.github/workflows/alerts_publish_on_approve.yml` - Posts when issue is approved
- `.github/workflows/alerts_auto_publish.yml` - Auto-posts without review (new)

## Support

If you encounter issues:
1. Check GitHub Actions logs for detailed error messages
2. Verify all required secrets are set correctly
3. Test credentials manually using the test commands above
4. Review `config.json` for typos or invalid values
