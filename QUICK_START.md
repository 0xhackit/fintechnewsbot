# Quick Start Guide

## X API Free Tier Setup (5 minutes)

### Step 1: Get X API Credentials (Free)
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Sign in and click "Sign up for Free Account"
3. Create a new App
4. Go to "Keys and Tokens" tab
5. Copy these 4 values:
   - API Key (Consumer Key)
   - API Secret (Consumer Secret)
   - Access Token
   - Access Token Secret

### Step 2: Add to GitHub Secrets
1. Go to your repo: Settings → Secrets and variables → Actions
2. Click "New repository secret" and add each:
   - Name: `X_API_KEY` → Value: [your API Key]
   - Name: `X_API_SECRET` → Value: [your API Secret]
   - Name: `X_ACCESS_TOKEN` → Value: [your Access Token]
   - Name: `X_ACCESS_SECRET` → Value: [your Access Token Secret]

### Step 3: You're Done!
The workflows are already configured. Next time an alert is approved, it will post to both Telegram and X automatically.

## Free Tier Limits
- ✅ **50 posts per day** (1,500/month)
- ✅ Resets at midnight UTC
- ✅ Perfect for ~2-3 alerts per hour

## Configuration Options

Edit `config.json`:

```json
{
  "alerts": {
    "auto_approve": false,        // false = manual review (recommended for free tier)
    "post_to_telegram": true,     // Keep Telegram enabled
    "post_to_x": true              // Enable X posting
  }
}
```

### Recommended Settings for Free Tier
```json
{
  "alerts": {
    "auto_approve": false,        // ⭐ Use manual review to control post volume
    "post_to_telegram": true,
    "post_to_x": true
  }
}
```

With `auto_approve: false`:
- You review each alert via GitHub issues
- Only approved alerts get posted
- Easy to stay under 50 posts/day
- Better quality control

## Testing

After adding secrets, test by:
1. Wait for next scheduled run (every 5 minutes)
2. A GitHub issue will be created for new alerts
3. Add label `approve` to the issue
4. Check Telegram and X - post should appear on both!

## Monitoring Usage

Check your X API usage:
- Go to https://developer.twitter.com/en/portal/dashboard
- Click on your app → "Usage" tab
- Monitor daily post count

## Need Help?

See full documentation: `docs/ALERTS_CONFIG.md`
