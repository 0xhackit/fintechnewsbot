/**
 * Twitter API v2 posting with OAuth 1.0a.
 * Reimplementation of publish_x.py's _post_to_x() in TypeScript.
 */

import OAuth from "oauth-1.0a";
import crypto from "crypto";

export interface TweetResult {
  tweetId: string;
  tweetUrl: string;
  tweetText: string;
}

/**
 * Post a tweet using Twitter API v2 with OAuth 1.0a User Context.
 */
export async function postTweet(text: string): Promise<TweetResult> {
  const apiKey = process.env.X_API_KEY;
  const apiSecret = process.env.X_API_SECRET;
  const accessToken = process.env.X_ACCESS_TOKEN;
  const accessSecret = process.env.X_ACCESS_SECRET;

  if (!apiKey || !apiSecret || !accessToken || !accessSecret) {
    throw new Error("Missing X API credentials (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)");
  }

  const oauth = new OAuth({
    consumer: { key: apiKey, secret: apiSecret },
    signature_method: "HMAC-SHA1",
    hash_function(baseString: string, key: string) {
      return crypto.createHmac("sha1", key).update(baseString).digest("base64");
    },
  });

  const token = { key: accessToken, secret: accessSecret };

  const requestData = {
    url: "https://api.twitter.com/2/tweets",
    method: "POST" as const,
  };

  const authHeader = oauth.toHeader(oauth.authorize(requestData, token));

  const response = await fetch("https://api.twitter.com/2/tweets", {
    method: "POST",
    headers: {
      ...authHeader,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (response.status === 402) {
    throw new Error(
      "X API Credits Depleted. Free Tier limits: 1,500 posts/month (50/day). " +
        "Check https://developer.twitter.com/en/portal/dashboard"
    );
  }

  if (response.status === 403) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as Record<string, string>).detail || "";
    if (detail.toLowerCase().includes("oauth1-permissions")) {
      throw new Error(
        "X API Permission Error: App needs 'Read and Write' OAuth 1.0a permissions. " +
          "Fix at: https://developer.twitter.com/en/portal/projects-and-apps"
      );
    }
    throw new Error(`X API error 403: ${JSON.stringify(body)}`);
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(`X API error ${response.status}: ${errorText}`);
  }

  const result = (await response.json()) as {
    data?: { id?: string };
  };

  const tweetId = result?.data?.id;
  if (!tweetId) {
    throw new Error("X API returned no tweet ID");
  }

  return {
    tweetId,
    tweetUrl: `https://x.com/i/web/status/${tweetId}`,
    tweetText: text,
  };
}
