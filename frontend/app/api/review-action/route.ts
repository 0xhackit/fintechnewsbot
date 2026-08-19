import { NextRequest, NextResponse } from "next/server";
import { sendTelegramMessage, formatTelegramMessage } from "@/lib/telegram";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";
import type { FeedEntry, Feed } from "@/lib/feed";

// Admin action on a v2 REVIEW item (the only bucket a human touches — KEEP posts
// automatically, KILLED is already dropped):
//   • publish → post to Telegram + add to the website feed (the feed IS the site).
//   • kill    → register in dedup state so the pipeline never resurfaces it.
// The item carries the same canonical id (SHA-1 title|canonical_url) that
// prepare_alerts_v2.py writes, so dedup stays consistent across the whole system.

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  return req.headers.get("authorization") === `Bearer ${password}`;
}

type Body = {
  action?: "publish" | "kill";
  id?: string;
  title?: string;
  link?: string;
  snippet?: string;
  score?: number;
  category?: string;
  source?: string;
  feed_name?: string;
  published_at?: string;
};

/** Add an item to state/seen_alerts.json so the automated pipeline skips it. */
async function registerSeen(id: string, title: string, link: string): Promise<boolean> {
  try {
    const stateFile = await getFileFromGitHub("state/seen_alerts.json");
    const state = JSON.parse(stateFile.content) as {
      seen?: string[];
      seen_titles?: { title: string; link: string; id: string }[];
    };
    const seen = new Set(state.seen || []);
    if (!seen.has(id)) {
      seen.add(id);
      state.seen = Array.from(seen).sort();
      const titles = state.seen_titles || [];
      titles.push({ title, link, id });
      state.seen_titles = titles.slice(-500);
      await putFileToGitHub(
        "state/seen_alerts.json",
        JSON.stringify(state, null, 2),
        stateFile.sha,
        `chore: register review action in dedup state`
      );
    }
    return true;
  } catch (err) {
    console.error("Dedup state update failed:", err);
    return false;
  }
}

/** Fire-and-forget preference signal for the ranking heuristics / future tuning. */
async function recordFeedback(
  title: string,
  category: string,
  signal: "positive" | "negative",
  reason: string
): Promise<void> {
  try {
    const fbFile = await getFileFromGitHub("state/feedback.json");
    const fb = JSON.parse(fbFile.content);
    fb.signals.push({
      title,
      category: category || "other",
      tier: signal === "positive" ? "high" : "unknown",
      signal,
      reason,
      timestamp: new Date().toISOString(),
    });
    if (fb.signals.length > 100) fb.signals = fb.signals.slice(-100);
    fb.updated_at = new Date().toISOString();
    await putFileToGitHub(
      "state/feedback.json",
      JSON.stringify(fb, null, 2),
      fbFile.sha,
      `chore: record review ${reason}`
    );
  } catch {
    // Feedback is best-effort.
  }
}

export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { action, id, title, link } = body;
  if (!action || !id || !title || !link) {
    return NextResponse.json(
      { error: "Missing action, id, title or link" },
      { status: 400 }
    );
  }

  // ── KILL ──────────────────────────────────────────────────────────────
  if (action === "kill") {
    const dedupUpdated = await registerSeen(id, title, link);
    await recordFeedback(title, body.category || "other", "negative", "review_killed");
    return NextResponse.json({ success: true, action, dedupUpdated });
  }

  // ── PUBLISH ───────────────────────────────────────────────────────────
  if (action === "publish") {
    // 1. Post to Telegram (mirrors the website feed). Bail if Telegram fails.
    const tg = await sendTelegramMessage(
      formatTelegramMessage(title, body.snippet || "", link)
    );
    if (!tg.success) {
      return NextResponse.json(
        { error: `Telegram failed: ${tg.error || "unknown"}` },
        { status: 502 }
      );
    }

    // 2. Add to the website feed (out/feed.json).
    let feedUpdated = false;
    try {
      const file = await getFileFromGitHub("out/feed.json");
      const feed: Feed = JSON.parse(file.content);
      const now = new Date().toISOString();
      const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

      const entry: FeedEntry = {
        id,
        title,
        link,
        snippet: body.snippet || "",
        score: body.score ?? 0,
        matched_topics: [],
        category: (body.category as FeedEntry["category"]) || undefined,
        posted_at: now,
        source: body.source || "",
        feed_name: body.feed_name || "",
        published_at: body.published_at || now,
        posted_to_telegram: true,
        telegram_message_id: tg.messageId,
        posted_to_x: false,
        tweet_id: null,
        tweet_text: null,
        tweet_url: null,
      };

      const entries = [entry, ...feed.entries.filter((e) => e.id !== id)]
        .filter((e) => new Date(e.posted_at).getTime() > sevenDaysAgo)
        .sort(
          (a, b) =>
            new Date(b.posted_at).getTime() - new Date(a.posted_at).getTime()
        );

      await putFileToGitHub(
        "out/feed.json",
        JSON.stringify({ updated_at: now, entries }, null, 2),
        file.sha,
        `chore: publish reviewed item — ${title.slice(0, 50)}`
      );
      feedUpdated = true;
    } catch (err) {
      console.error("Feed update failed:", err);
    }

    // 3. Register in dedup so the pipeline won't repost it.
    const dedupUpdated = await registerSeen(id, title, link);
    await recordFeedback(title, body.category || "other", "positive", "review_published");

    return NextResponse.json({
      success: true,
      action,
      telegram: { success: tg.success, messageId: tg.messageId },
      feedUpdated,
      dedupUpdated,
    });
  }

  return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
}
