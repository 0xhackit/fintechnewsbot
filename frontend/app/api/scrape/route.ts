import { NextRequest, NextResponse } from "next/server";
import { scrapeUrl } from "@/lib/scraper";
import { generateTweet } from "@/lib/ai";

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const auth = req.headers.get("authorization");
  return auth === `Bearer ${password}`;
}

export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as { url?: string };
    const url = body.url?.trim();

    if (!url) {
      return NextResponse.json({ error: "Missing url" }, { status: 400 });
    }

    // Validate URL format
    try {
      new URL(url);
    } catch {
      return NextResponse.json({ error: "Invalid URL" }, { status: 400 });
    }

    // Scrape metadata
    const metadata = await scrapeUrl(url);

    // Generate AI tweet
    const tweet = await generateTweet(metadata.title, metadata.snippet);

    return NextResponse.json({
      title: metadata.title,
      snippet: metadata.snippet,
      ogImage: metadata.ogImage,
      source: metadata.source,
      url: metadata.url,
      tweetText: tweet.text,
      tweetStyle: tweet.styleUsed,
    });
  } catch (err) {
    console.error("Scrape error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Scrape failed" },
      { status: 500 }
    );
  }
}
