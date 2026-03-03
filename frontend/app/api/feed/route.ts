import { NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";

const PROD_FEED_URL =
  "https://raw.githubusercontent.com/0xhackit/fintechnewsbot/main/out/feed.json";

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
