import { NextRequest, NextResponse } from "next/server";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";
import type { Feed } from "@/lib/feed";

// Manual editorial boost on an already-posted item. The pipeline's score is a
// deterministic proxy for importance and it gets things wrong in both
// directions — a genuinely big story can land at 35 while a firehose relay
// lands at 69. Boost is the human override: it is added to the pipeline score
// for ranking only, so a boosted story can take the lead slot or a top-three
// place in the brief without anything being rewritten or reposted.
//
// Stored on the feed entry as `boost`. feed_writer.upsert_entries merges with
// dict.update(), which only overwrites keys present in the incoming entry — so
// a later pipeline run touching the same id leaves the boost intact.

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  return req.headers.get("authorization") === `Bearer ${password}`;
}

/** Keep a boost from silently becoming a permanent #1 pin. */
const MAX_BOOST = 200;
const MIN_BOOST = -200;

export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let id: string | undefined;
  let boost: unknown;
  try {
    ({ id, boost } = (await req.json()) as { id?: string; boost?: unknown });
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  if (!id) {
    return NextResponse.json({ error: "Missing entry id" }, { status: 400 });
  }
  if (typeof boost !== "number" || !Number.isFinite(boost)) {
    return NextResponse.json({ error: "boost must be a number" }, { status: 400 });
  }

  const clamped = Math.round(Math.max(MIN_BOOST, Math.min(MAX_BOOST, boost)));

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

  if (clamped === 0) {
    delete entry.boost;
  } else {
    entry.boost = clamped;
  }
  feed.updated_at = new Date().toISOString();

  const effective = (entry.score ?? 0) + clamped;
  const verb = clamped === 0 ? "clear boost" : `boost ${clamped > 0 ? "+" : ""}${clamped}`;

  try {
    await putFileToGitHub(
      "out/feed.json",
      JSON.stringify(feed, null, 2),
      file.sha,
      `chore: ${verb} — ${(entry.title || "").slice(0, 50)}`
    );
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Feed write failed" },
      { status: 502 }
    );
  }

  return NextResponse.json({
    success: true,
    id,
    boost: clamped,
    baseScore: entry.score ?? 0,
    effectiveScore: effective,
  });
}
