import { NextRequest, NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";

// Serves the market/editorial reports produced offline. Read-only.
//   ?source=feed (published feed) | items (current candidates)   → scripts/shadow_market.py
//   ?source=standalone (v2 pipeline: regions + content lanes + tiers) → scripts/standalone_pipeline.py
// Default: feed.

const SOURCES = ["feed", "items", "standalone"] as const;
type Source = (typeof SOURCES)[number];

function marketDir(source: Source, name: string): string {
  return join(process.cwd(), "..", "out", "market", source, `${name}.json`);
}

function readJson<T>(source: Source, name: string, fallback: T): T {
  try {
    return JSON.parse(readFileSync(marketDir(source, name), "utf-8"));
  } catch {
    return fallback;
  }
}

export async function GET(req: NextRequest) {
  const param = req.nextUrl.searchParams.get("source");
  const source: Source = SOURCES.includes(param as Source) ? (param as Source) : "feed";

  const kept = readJson(source, "kept", [] as unknown[]);
  const killed = readJson(source, "killed", [] as unknown[]);
  const review = readJson(source, "review", [] as unknown[]);
  const meta = readJson(source, "meta", null);
  const total = kept.length + killed.length + review.length;

  return NextResponse.json(
    { source, kept, killed, review, total, generated: total > 0, meta },
    { headers: { "Cache-Control": "no-store" } }
  );
}
