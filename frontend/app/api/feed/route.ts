import { NextRequest, NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";
import type { Feed } from "@/lib/feed";

const PROD_FEED_URL =
  "https://raw.githubusercontent.com/0xhackit/fintechnewsbot/main/out/feed.json";

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const auth = req.headers.get("authorization");
  return auth === `Bearer ${password}`;
}

export async function GET() {
  try {
    if (process.env.NODE_ENV === "development") {
      // Dev: read from local filesystem
      const feedPath = join(process.cwd(), "..", "out", "feed.json");
      const data = readFileSync(feedPath, "utf-8");
      return NextResponse.json(JSON.parse(data));
    }

    // Production: fetch from GitHub (fresh, no cache)
    const resp = await fetch(PROD_FEED_URL, { cache: "no-store" });
    if (!resp.ok) throw new Error(`GitHub feed fetch failed: ${resp.status}`);
    const data = await resp.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ updated_at: "", entries: [] });
  }
}

export async function DELETE(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as { id?: string };
    const { id } = body;

    if (!id) {
      return NextResponse.json({ error: "Missing entry id" }, { status: 400 });
    }

    const file = await getFileFromGitHub("out/feed.json");
    const feed: Feed = JSON.parse(file.content);

    const entry = feed.entries.find((e) => e.id === id);
    if (!entry) {
      return NextResponse.json({ error: "Entry not found" }, { status: 404 });
    }

    const title = entry.title || "unknown";
    feed.entries = feed.entries.filter((e) => e.id !== id);
    feed.updated_at = new Date().toISOString();

    await putFileToGitHub(
      "out/feed.json",
      JSON.stringify(feed, null, 2),
      file.sha,
      `chore: delete post — ${title.slice(0, 50)}`
    );

    // Auto-record negative feedback (fire-and-forget)
    try {
      const fbFile = await getFileFromGitHub("state/feedback.json");
      const fb = JSON.parse(fbFile.content);
      fb.signals.push({
        title,
        category: entry.ai_category || "other",
        tier: "unknown",
        signal: "negative",
        reason: "deleted",
        timestamp: new Date().toISOString(),
      });
      if (fb.signals.length > 100) fb.signals = fb.signals.slice(-100);
      fb.updated_at = new Date().toISOString();
      await putFileToGitHub(
        "state/feedback.json",
        JSON.stringify(fb, null, 2),
        fbFile.sha,
        `chore: record delete feedback`
      );
    } catch {
      // Feedback is best-effort — don't fail the delete
    }

    return NextResponse.json({ success: true, deleted: title });
  } catch (err) {
    console.error("Feed delete error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Delete failed" },
      { status: 500 }
    );
  }
}
