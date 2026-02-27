import { NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";

export async function GET() {
  try {
    // In dev, serve from the local out/feed.json (one level up from frontend/)
    const feedPath = join(process.cwd(), "..", "out", "feed.json");
    const data = readFileSync(feedPath, "utf-8");
    return NextResponse.json(JSON.parse(data));
  } catch {
    return NextResponse.json({ updated_at: "", entries: [] });
  }
}
