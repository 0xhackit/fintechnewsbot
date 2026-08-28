import { NextRequest, NextResponse } from "next/server";
import { deleteTelegramMessage } from "@/lib/telegram";
import { deleteTweet } from "@/lib/twitter";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";
import type { Feed } from "@/lib/feed";

// Retract an item that ALREADY posted — the escape hatch for anything the
// deterministic gate let through (a tier-C firehose tweet that cleared the
// gate on a big dollar figure, say). Unlike DELETE /api/feed, which only drops
// the website entry, this pulls the item off every surface it reached:
//
//   website  → remove the entry from out/feed.json (always attempted)
//   Telegram → deleteMessage on the stored telegram_message_id
//   X        → DELETE /2/tweets on the stored tweet_id
//
// Per-surface and fail-soft: Telegram refuses posts older than 48h and X can
// rate-limit, but neither should strand the item on the website. Each surface
// reports its own outcome so the admin sees exactly what is still live.

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  return req.headers.get("authorization") === `Bearer ${password}`;
}

type SurfaceResult = { attempted: boolean; success: boolean; error?: string };

/** Negative preference signal, mirroring DELETE /api/feed. Best-effort. */
async function recordFeedback(title: string, category: string): Promise<void> {
  try {
    const fbFile = await getFileFromGitHub("state/feedback.json");
    const fb = JSON.parse(fbFile.content);
    fb.signals.push({
      title,
      category: category || "other",
      tier: "unknown",
      signal: "negative",
      reason: "retracted",
      timestamp: new Date().toISOString(),
    });
    if (fb.signals.length > 100) fb.signals = fb.signals.slice(-100);
    fb.updated_at = new Date().toISOString();
    await putFileToGitHub(
      "state/feedback.json",
      JSON.stringify(fb, null, 2),
      fbFile.sha,
      `chore: record retract feedback`
    );
  } catch {
    // Feedback never blocks a retraction.
  }
}

export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let id: string | undefined;
  try {
    ({ id } = (await req.json()) as { id?: string });
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  if (!id) {
    return NextResponse.json({ error: "Missing entry id" }, { status: 400 });
  }

  // Read the feed first — it carries the message/tweet ids we need to retract.
  let file: { content: string; sha: string };
  try {
    file = await getFileFromGitHub("out/feed.json");
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Feed read failed" },
      { status: 502 }
    );
  }

  const feed: Feed = JSON.parse(file.content);
  const entry = feed.entries.find((e) => e.id === id);
  if (!entry) {
    return NextResponse.json({ error: "Entry not found in feed" }, { status: 404 });
  }

  const telegram: SurfaceResult = { attempted: false, success: false };
  const x: SurfaceResult = { attempted: false, success: false };

  // ── Telegram ────────────────────────────────────────────────────────────
  if (entry.posted_to_telegram && entry.telegram_message_id) {
    telegram.attempted = true;
    const res = await deleteTelegramMessage(entry.telegram_message_id);
    telegram.success = res.success;
    if (!res.success) telegram.error = res.error;
  }

  // ── X ───────────────────────────────────────────────────────────────────
  if (entry.posted_to_x && entry.tweet_id) {
    x.attempted = true;
    try {
      const res = await deleteTweet(entry.tweet_id);
      x.success = res.deleted;
      if (!res.deleted) x.error = "X reported the tweet was not deleted";
    } catch (err) {
      x.error = err instanceof Error ? err.message : "Unknown X error";
    }
  }

  // ── Website ─────────────────────────────────────────────────────────────
  // Last, so a failed remote delete is still reflected against a live entry
  // if this write throws — better a stale card than a silent half-retraction.
  const title = entry.title || "unknown";
  feed.entries = feed.entries.filter((e) => e.id !== id);
  feed.updated_at = new Date().toISOString();

  try {
    await putFileToGitHub(
      "out/feed.json",
      JSON.stringify(feed, null, 2),
      file.sha,
      `chore: retract post — ${title.slice(0, 50)}`
    );
  } catch (err) {
    return NextResponse.json(
      {
        error: err instanceof Error ? err.message : "Feed write failed",
        website: { attempted: true, success: false },
        telegram,
        x,
      },
      { status: 502 }
    );
  }

  await recordFeedback(title, entry.category || entry.ai_category || "other");

  return NextResponse.json({
    success: true,
    retracted: title,
    website: { attempted: true, success: true },
    telegram,
    x,
  });
}
