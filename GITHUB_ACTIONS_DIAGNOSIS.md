# GitHub Actions Diagnosis - Why Telegram Posts Stopped

**Date:** January 23, 2026
**Last Successful Post:** January 21, 2026 09:54 UTC
**Days Without Posts:** 2 days

---

## Problem Summary

Your Telegram alerts system stopped posting on **Jan 21 at 09:54**. The bot commits show regular activity until that time, then stopped completely.

## Root Causes Identified

### 1. **TOO MANY CONFLICTING WORKFLOWS** ⚠️

You have **5 workflows**, 3 of which run every 5 minutes:

| Workflow | Schedule | Purpose | Status |
|----------|----------|---------|--------|
| `alerts.yml` | Every 5 min | OLD - Runs `run_alerts.py` without posting | ❌ **REDUNDANT** |
| `alerts_prepare.yml` | Every 5 min | Creates GitHub issues when `auto_approve=false` | ❌ **WRONG MODE** |
| `alerts_auto_publish.yml` | Every 5 min | Auto-posts when `auto_approve=true` | ✅ **CORRECT** |
| `alerts_publish_on_approve.yml` | On issue label | Posts when issue gets `approve` label | ❌ **WRONG MODE** |
| `daily.yml` | Daily 08:00 | Runs `run.py` to fetch news | ❌ **REDUNDANT** |

**The Problem:**
- With `auto_approve: true` in config, only `alerts_auto_publish.yml` should run
- But `alerts.yml` and `alerts_prepare.yml` are ALSO running every 5 minutes
- This creates race conditions and state conflicts
- Multiple workflows fighting over the same files

### 2. **Workflow Logic Issues**

**alerts_prepare.yml** (Line 56-106):
```yaml
- name: Prepare alert drafts
  if: steps.check_config.outputs.auto_approve != 'true'  # Only if FALSE
  run: python scripts/run_alerts.py --mode prepare

- name: Skip message
  if: steps.check_config.outputs.auto_approve == 'true'  # Your config!
  run: echo "⏭️  Auto-approve is enabled - skipping manual approval"
```

**This workflow runs but does NOTHING** because your `auto_approve: true` makes it skip all steps!

**alerts.yml** (Line 42-47):
```yaml
- name: Run alerts pipeline
  run: python scripts/run_alerts.py
```

**This workflow has NO CONFIG CHECK** - it always runs `run_alerts.py`, which:
- ✅ Prepares drafts
- ❌ Does NOT post to Telegram
- ❌ Wastes GitHub Actions minutes
- ❌ Updates state, potentially blocking other workflows

### 3. **Why It Stopped on Jan 21**

Looking at your git log, on Jan 21 you made **10+ manual commits**:
```
ed08a5d Fix UI issues
19c4345 Improve terminal UI
608d863 Force deployment
8008978 Add Vercel configuration
7984555 Transform UI to terminal-style
...
```

**What Likely Happened:**
1. All those commits triggered workflow runs
2. Multiple workflows ran simultaneously (concurrency issues)
3. One workflow may have encountered an error
4. GitHub Actions might have rate-limited or disabled workflows
5. The `alerts_auto_publish.yml` workflow stopped running

### 4. **Missing Error Handling**

The workflows have **NO error logging or notifications**:
- If Telegram API fails → silent failure
- If `run.py` fails → silent failure
- If drafts are empty → silent failure
- No Slack/Discord/Email notifications on failures

---

## Current Workflow Analysis

### alerts_auto_publish.yml (CORRECT WORKFLOW)

**Should run every 5 minutes when `auto_approve: true`**

Steps:
1. ✅ Checkout code
2. ✅ Check config (`auto_approve: true`)
3. ✅ Run `python run.py` (fetch news)
4. ✅ Run `python scripts/run_alerts.py --mode prepare` (create drafts)
5. ✅ Post drafts to Telegram
6. ✅ Commit state changes

**Issues:**
- No error handling
- No retry logic
- No failure notifications
- Inline Python script instead of using existing `post_alerts_now.py`

### alerts.yml (REDUNDANT - DELETE)

**Runs every 5 minutes, always**

Problems:
- Doesn't check `auto_approve` config
- Only runs `run_alerts.py` (prepares drafts, doesn't post)
- Creates conflicts with `alerts_auto_publish.yml`
- Wastes GitHub Actions minutes

**Recommendation:** ❌ **DELETE THIS FILE**

### alerts_prepare.yml (WRONG MODE - DELETE)

**Runs every 5 minutes when `auto_approve: false`**

Since your config has `auto_approve: true`, this workflow:
- Runs every 5 minutes
- Checks config
- Skips ALL steps
- Does nothing but waste resources

**Recommendation:** ❌ **DELETE THIS FILE** (you're using auto-approve mode)

### alerts_publish_on_approve.yml (WRONG MODE - DELETE)

**Triggered when GitHub issue gets `approve` label**

Since your config has `auto_approve: true`:
- You don't create approval issues
- This workflow never triggers
- Just taking up space

**Recommendation:** ❌ **DELETE THIS FILE** (you're using auto-approve mode)

### daily.yml (REDUNDANT - DELETE)

**Runs `python run.py` daily at 08:00 UTC**

Problem:
- `alerts_auto_publish.yml` already runs `run.py` every 5 minutes
- This is completely redundant
- Wastes GitHub Actions minutes

**Recommendation:** ❌ **DELETE THIS FILE**

---

## Recommended Solution

### Step 1: Delete Redundant Workflows

**Keep ONLY:**
- `alerts_auto_publish.yml` (the correct one)

**Delete:**
- `alerts.yml`
- `alerts_prepare.yml`
- `alerts_publish_on_approve.yml`
- `daily.yml`

### Step 2: Fix alerts_auto_publish.yml

**Issues to fix:**
1. Use the existing `post_alerts_now.py` instead of inline script
2. Add error handling
3. Add failure notifications
4. Add retry logic

**Proposed changes:**

```yaml
- name: Post to Telegram
  if: steps.check_config.outputs.auto_approve == 'true' && steps.check_config.outputs.post_telegram == 'true'
  env:
    TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
    TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
  run: |
    if [ -f out/alerts_drafts.json ]; then
      DRAFT_COUNT=$(python -c "import json; print(len(json.load(open('out/alerts_drafts.json'))))")
      echo "📋 Found $DRAFT_COUNT draft(s)"

      if [ "$DRAFT_COUNT" -gt "0" ]; then
        # Use the dedicated posting script
        python post_alerts_now.py || {
          echo "❌ Failed to post to Telegram"
          exit 1
        }
      else
        echo "📭 No drafts to post (all filtered or seen)"
      fi
    else
      echo "⚠️  No drafts file found - pipeline may have failed"
      exit 1
    fi
```

### Step 3: Add Monitoring

Add a notification step:

```yaml
- name: Notify on failure
  if: failure()
  run: |
    echo "❌ Workflow failed!"
    # TODO: Add Slack/Discord webhook notification
```

### Step 4: Verify GitHub Secrets

Ensure these secrets exist in GitHub repo settings:

- `TG_API_ID` - Telegram API ID
- `TG_API_HASH` - Telegram API hash
- `TELEGRAM_BOT_TOKEN` - Bot token
- `TELEGRAM_CHAT_ID` - Group chat ID

### Step 5: Manually Trigger Workflow

After cleanup:

```bash
# Via GitHub UI
Go to: Actions → Auto-Publish Alerts → Run workflow

# Or via gh CLI (if installed)
gh workflow run alerts_auto_publish.yml
```

---

## Testing Plan

### 1. Local Test (Before deploying)

```bash
# Fetch fresh news
python3 run.py

# Generate alerts
python3 scripts/run_alerts.py --mode prepare

# Check drafts
cat out/alerts_drafts.json | jq '.[] | .title'

# Post manually
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python3 post_alerts_now.py
```

### 2. GitHub Actions Test

After deleting redundant workflows:

1. Commit changes
2. Push to GitHub
3. Wait 5 minutes
4. Check Actions tab for workflow run
5. Verify Telegram post
6. Check bot commit (`chore: update alerts state`)

### 3. Monitor for 24 Hours

Check every few hours:
- GitHub Actions runs successfully
- Telegram receives posts
- State file updates
- No duplicate posts

---

## File Cleanup Checklist

- [ ] Delete `.github/workflows/alerts.yml`
- [ ] Delete `.github/workflows/alerts_prepare.yml`
- [ ] Delete `.github/workflows/alerts_publish_on_approve.yml`
- [ ] Delete `.github/workflows/daily.yml`
- [ ] Keep `.github/workflows/alerts_auto_publish.yml`
- [ ] Update `alerts_auto_publish.yml` to use `post_alerts_now.py`
- [ ] Add error handling to workflow
- [ ] Verify GitHub secrets are set
- [ ] Test manually
- [ ] Commit and push
- [ ] Monitor for 24h

---

## Expected Behavior After Fix

**Every 5 minutes:**
1. Workflow triggers
2. Fetches fresh news from RSS/Telegram
3. Scores and filters items
4. Generates drafts for items with score ≥ 35
5. Posts NEW drafts to Telegram (not seen before)
6. Updates state file
7. Commits state to git

**You should see:**
- Regular bot commits every 5-60 minutes (depending on new news)
- Telegram posts for high-quality stories (funding, launches, M&A)
- No duplicate posts (deduplication working)
- No spam (low-score items filtered)

---

## Current Status Summary

| Component | Status | Issue |
|-----------|--------|-------|
| Config | ✅ OK | `auto_approve: true`, `MIN_ALERT_SCORE: 35` |
| Local Pipeline | ✅ OK | Generates 8 drafts successfully |
| Posting Script | ✅ OK | `post_alerts_now.py` works |
| Workflows | ❌ BROKEN | Too many conflicting workflows |
| GitHub Actions | ❌ STOPPED | Last run Jan 21 09:54 |
| Telegram Posts | ❌ STOPPED | No posts for 2 days |

---

## Next Steps

**Immediate (Do Now):**
1. ✅ Post the 8 pending alerts manually with `post_alerts_now.py`
2. ❌ Delete 4 redundant workflows
3. 🔧 Fix `alerts_auto_publish.yml`
4. ✅ Verify GitHub secrets
5. 🧪 Test workflow manually

**Short-term (This Week):**
1. Add failure notifications (Slack/Discord)
2. Add retry logic for Telegram API failures
3. Add workflow run monitoring
4. Document the streamlined setup

**Long-term (Future):**
1. Consider moving to a dedicated server (Railway/Render)
2. Add more robust error handling
3. Add metrics/logging
4. Set up alerts for workflow failures
