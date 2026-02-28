import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { postTweet } from "@/lib/twitter";
import {
  sendTelegramMessage,
  formatTelegramMessage,
} from "@/lib/telegram";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";
import type { FeedEntry, Feed } from "@/lib/feed";

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const auth = req.headers.get("authorization");
  return auth === `Bearer ${password}`;
}

function generateId(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
}

/**
 * Compute the same stable_item_id as run_alerts.py:
 *   SHA-1 of "title.lower()|url.lower()"
 */
function stableItemId(title: string, url: string): string {
  const base = `${title.trim().toLowerCase()}|${url.trim().toLowerCase()}`;
  return crypto.createHash("sha1").update(base).digest("hex");
}

export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as {
      title?: string;
      snippet?: string;
      url?: string;
      source?: string;
      tweetText?: string;
    };

    const { title, snippet, url, source, tweetText } = body;

    if (!title || !url) {
      return NextResponse.json(
        { error: "Missing title or url" },
        { status: 400 }
      );
    }

    // Post to X and Telegram in parallel
    const [xResult, tgResult] = await Promise.allSettled([
      tweetText ? postTweet(tweetText) : Promise.reject(new Error("No tweet text")),
      sendTelegramMessage(formatTelegramMessage(title, snippet || "", url)),
    ]);

    const xOutcome =
      xResult.status === "fulfilled"
        ? {
            success: true,
            tweetId: xResult.value.tweetId,
            tweetUrl: xResult.value.tweetUrl,
          }
        : { success: false, error: (xResult.reason as Error).message };

    const tgOutcome =
      tgResult.status === "fulfilled"
        ? tgResult.value
        : { success: false, messageId: 0, error: (tgResult.reason as Error).message };

    // Persist to feed via GitHub
    let feedUpdated = false;
    try {
      const file = await getFileFromGitHub("out/feed.json");
      const feed: Feed = JSON.parse(file.content);

      const now = new Date().toISOString();
      const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

      const newEntry: FeedEntry = {
        id: generateId(title),
        title,
        link: url,
        snippet: snippet || "",
        score: 100,
        matched_topics: [],
        ai_category: "manual",
        feed_name: "manual",
        posted_at: now,
        source: source || "",
        published_at: now,
        posted_to_telegram: tgOutcome.success,
        telegram_message_id:
          tgOutcome.success ? tgOutcome.messageId : null,
        posted_to_x:
          xOutcome.success,
        tweet_id:
          xOutcome.success && "tweetId" in xOutcome
            ? xOutcome.tweetId
            : null,
        tweet_text: tweetText || null,
        tweet_url:
          xOutcome.success && "tweetUrl" in xOutcome
            ? xOutcome.tweetUrl
            : null,
      };

      // Add new entry, prune old, sort desc
      const entries = [newEntry, ...feed.entries]
        .filter((e) => new Date(e.posted_at).getTime() > sevenDaysAgo)
        .sort(
          (a, b) =>
            new Date(b.posted_at).getTime() - new Date(a.posted_at).getTime()
        );

      const updated: Feed = { updated_at: now, entries };

      await putFileToGitHub(
        "out/feed.json",
        JSON.stringify(updated, null, 2),
        file.sha,
        `chore: manual post — ${title.slice(0, 50)}`
      );
      feedUpdated = true;
    } catch (err) {
      console.error("Feed update failed:", err);
    }

    // ── Dedup: register in state/seen_alerts.json ──
    // This prevents the automated pipeline from reposting the same article.
    // Uses the same SHA-1(title|url) ID as run_alerts.py's stable_item_id().
    let dedupUpdated = false;
    try {
      const stateFile = await getFileFromGitHub("state/seen_alerts.json");
      const state = JSON.parse(stateFile.content) as {
        seen?: string[];
        seen_titles?: { title: string; link: string; id: string }[];
      };

      const itemId = stableItemId(title, url);
      const seenSet = new Set(state.seen || []);

      if (!seenSet.has(itemId)) {
        seenSet.add(itemId);
        state.seen = Array.from(seenSet).sort();

        // Add to seen_titles for fuzzy title similarity checks
        const seenTitles = state.seen_titles || [];
        seenTitles.push({ title, link: url, id: itemId });
        // Keep last 100 titles (same cap as run_alerts.py)
        state.seen_titles = seenTitles.slice(-100);

        await putFileToGitHub(
          "state/seen_alerts.json",
          JSON.stringify(state, null, 2),
          stateFile.sha,
          `chore: register manual post in dedup state`
        );
        dedupUpdated = true;
      } else {
        dedupUpdated = true; // Already present
      }
    } catch (err) {
      console.error("Dedup state update failed:", err);
    }

    return NextResponse.json({
      xResult: xOutcome,
      telegramResult: tgOutcome,
      feedUpdated,
      dedupUpdated,
    });
  } catch (err) {
    console.error("Manual post error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Post failed" },
      { status: 500 }
    );
  }
}
