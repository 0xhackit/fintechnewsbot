import { NextRequest, NextResponse } from "next/server";
import { postTweet } from "@/lib/twitter";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";
import type { Feed } from "@/lib/feed";

const COMPANY_HANDLES: Record<string, string> = {
  coinbase: "@coinbase",
  stripe: "@stripe",
  circle: "@circle",
  ripple: "@Ripple",
  paypal: "@PayPal",
  visa: "@Visa",
  mastercard: "@Mastercard",
  jpmorgan: "@jpmorgan",
  blackrock: "@BlackRock",
  revolut: "@RevolutApp",
  robinhood: "@RobinhoodApp",
  kraken: "@kaboracle",
  binance: "@binance",
  uniswap: "@Uniswap",
  aave: "@AaveAave",
};

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const auth = req.headers.get("authorization");
  return auth === `Bearer ${password}`;
}

function formatNewsTweet(title: string): string {
  let text = title.trim();
  for (const [company, handle] of Object.entries(COMPANY_HANDLES)) {
    const regex = new RegExp(`\\b${company}\\b`, "i");
    if (regex.test(text)) {
      text = text.replace(regex, handle);
      break;
    }
  }
  if (text.length > 280) text = text.slice(0, 277) + "...";
  return text;
}

export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as {
      id?: string;
      title?: string;
      link?: string;
    };

    if (!body.id || !body.title) {
      return NextResponse.json(
        { error: "Missing id or title" },
        { status: 400 }
      );
    }

    // Format and post tweet
    const tweetText = formatNewsTweet(body.title);
    const result = await postTweet(tweetText);

    // Update feed.json to mark as posted to X
    let feedUpdated = false;
    try {
      const file = await getFileFromGitHub("out/feed.json");
      const feed: Feed = JSON.parse(file.content);

      const entry = feed.entries.find((e) => e.id === body.id);
      if (entry) {
        entry.posted_to_x = true;
        entry.tweet_id = result.tweetId;
        entry.tweet_text = result.tweetText;
        entry.tweet_url = result.tweetUrl;
        feed.updated_at = new Date().toISOString();

        await putFileToGitHub(
          "out/feed.json",
          JSON.stringify(feed, null, 2),
          file.sha,
          `chore: promote to X — ${body.title.slice(0, 50)}`
        );
        feedUpdated = true;
      }
    } catch (err) {
      console.error("Feed update after promote failed:", err);
    }

    // Record positive feedback (fire-and-forget)
    try {
      const feedbackFile = await getFileFromGitHub("state/feedback.json");
      const feedback = JSON.parse(feedbackFile.content);
      feedback.signals.push({
        title: body.title,
        category: "promoted",
        tier: "high",
        signal: "positive",
        reason: "promoted_to_x",
        timestamp: new Date().toISOString(),
      });
      if (feedback.signals.length > 100) {
        feedback.signals = feedback.signals.slice(-100);
      }
      feedback.updated_at = new Date().toISOString();
      await putFileToGitHub(
        "state/feedback.json",
        JSON.stringify(feedback, null, 2),
        feedbackFile.sha,
        `chore: record promote-to-x feedback`
      );
    } catch {
      // Feedback recording is best-effort
    }

    return NextResponse.json({
      success: true,
      tweetUrl: result.tweetUrl,
      tweetId: result.tweetId,
      feedUpdated,
    });
  } catch (err) {
    console.error("Promote to X error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Post failed" },
      { status: 500 }
    );
  }
}
