import { NextRequest, NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";

// Serves the v2 pipeline's review-queue report (kept/killed/review). In production
// these files are produced every run by `scripts/prepare_alerts_v2.py` and committed
// to the repo, so we read them fresh from GitHub raw (like /api/feed). In dev we read
// the local working tree. Read-only, admin (/dashboard) only.

const SOURCES = ["standalone"] as const;
type Source = (typeof SOURCES)[number];

const RAW_BASE =
  "https://raw.githubusercontent.com/0xhackit/fintechnewsbot/main/out/market";

function readLocal<T>(source: Source, name: string, fallback: T): T {
  try {
    const path = join(process.cwd(), "..", "out", "market", source, `${name}.json`);
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return fallback;
  }
}

async function readRemote<T>(source: Source, name: string, fallback: T): Promise<T> {
  try {
    const resp = await fetch(`${RAW_BASE}/${source}/${name}.json`, { cache: "no-store" });
    if (!resp.ok) return fallback;
    return (await resp.json()) as T;
  } catch {
    return fallback;
  }
}

export async function GET(req: NextRequest) {
  const param = req.nextUrl.searchParams.get("source");
  const source: Source = SOURCES.includes(param as Source) ? (param as Source) : "standalone";

  const isDev = process.env.NODE_ENV === "development";
  const names = ["kept", "killed", "review", "meta"] as const;
  const [kept, killed, review, meta] = isDev
    ? names.map((n) => readLocal(source, n, n === "meta" ? null : ([] as unknown[])))
    : await Promise.all(
        names.map((n) => readRemote(source, n, n === "meta" ? null : ([] as unknown[])))
      );

  const total =
    (kept as unknown[]).length + (killed as unknown[]).length + (review as unknown[]).length;

  return NextResponse.json(
    { source, kept, killed, review, total, generated: total > 0, meta },
    { headers: { "Cache-Control": "no-store" } }
  );
}
