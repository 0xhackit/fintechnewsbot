/**
 * URL metadata scraping utility.
 * Fetches an article URL and extracts title, snippet, OG image, and full text.
 */

export interface ArticleMetadata {
  title: string;
  snippet: string;
  ogImage: string | null;
  source: string;
  url: string;
  fullText?: string;
}

/**
 * Scrape metadata from a URL.
 * Parses og:title, og:description, og:image with fallbacks.
 */
export async function scrapeUrl(
  url: string,
  options?: { extractFullText?: boolean }
): Promise<ArticleMetadata> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);

  try {
    // Rewrite Twitter/X URLs to FxTwitter for proper OG metadata
    const fetchUrl = rewriteTwitterUrl(url);
    const isTwitter = fetchUrl !== url;

    const resp = await fetch(fetchUrl, {
      signal: controller.signal,
      redirect: isTwitter ? "follow" : undefined,
      headers: {
        // FxTwitter serves OG metadata to bots, redirects browsers
        "User-Agent": isTwitter
          ? "Twitterbot/1.0"
          : "Mozilla/5.0 (compatible; FintechOnchain/1.0)",
      },
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }

    const html = await resp.text();
    const source = extractSource(url);

    // Extract metadata from HTML
    const title = extractOgTag(html, "og:title") || extractTitle(html) || "";
    const snippet =
      extractOgTag(html, "og:description") ||
      extractMetaDescription(html) ||
      extractFirstParagraph(html) ||
      "";
    const ogImageRaw = extractOgImage(html);
    const ogImage = ogImageRaw ? resolveUrl(ogImageRaw, url) : null;

    const result: ArticleMetadata = {
      title: decodeEntities(title).trim(),
      snippet: decodeEntities(snippet).trim().slice(0, 500),
      ogImage,
      source,
      url,
    };

    if (options?.extractFullText) {
      result.fullText = extractFullText(html).slice(0, 5000);
    }

    return result;
  } finally {
    clearTimeout(timeout);
  }
}

// ── Twitter/X URL rewriting ──

/**
 * Detect twitter.com / x.com URLs and rewrite to fxtwitter.com.
 * FxTwitter returns proper og:title (author), og:description (tweet text),
 * and og:image — unlike Twitter which requires JS rendering.
 */
function rewriteTwitterUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, "").replace(/^mobile\./, "");
    if (host === "twitter.com" || host === "x.com") {
      parsed.hostname = "fxtwitter.com";
      return parsed.toString();
    }
  } catch {
    // Invalid URL — return as-is
  }
  return url;
}

// ── HTML parsing helpers ──

function extractOgTag(html: string, property: string): string | null {
  // property="og:title" content="..."
  const m1 = html.match(
    new RegExp(
      `<meta\\s+[^>]*?property=["']${property}["'][^>]*?content=["']([^"']+)["']`,
      "i"
    )
  );
  if (m1) return m1[1];

  // content="..." property="og:title"
  const m2 = html.match(
    new RegExp(
      `<meta\\s+[^>]*?content=["']([^"']+)["'][^>]*?property=["']${property}["']`,
      "i"
    )
  );
  if (m2) return m2[1];

  return null;
}

function extractOgImage(html: string): string | null {
  return extractOgTag(html, "og:image");
}

function extractTitle(html: string): string | null {
  const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return m ? m[1].trim() : null;
}

function extractMetaDescription(html: string): string | null {
  const m = html.match(
    /<meta\s+[^>]*?name=["']description["'][^>]*?content=["']([^"']+)["']/i
  );
  if (m) return m[1];

  const m2 = html.match(
    /<meta\s+[^>]*?content=["']([^"']+)["'][^>]*?name=["']description["']/i
  );
  return m2 ? m2[1] : null;
}

function extractFirstParagraph(html: string): string | null {
  const m = html.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
  if (!m) return null;
  return stripTags(m[1]).trim().slice(0, 300);
}

function extractFullText(html: string): string {
  // Remove script and style tags
  let text = html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<nav[\s\S]*?<\/nav>/gi, "")
    .replace(/<header[\s\S]*?<\/header>/gi, "")
    .replace(/<footer[\s\S]*?<\/footer>/gi, "");
  text = stripTags(text);
  // Normalize whitespace
  return text.replace(/\s+/g, " ").trim();
}

function stripTags(html: string): string {
  return html.replace(/<[^>]+>/g, " ");
}

function decodeEntities(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)));
}

function resolveUrl(imageUrl: string, baseUrl: string): string {
  if (imageUrl.startsWith("//")) return "https:" + imageUrl;
  if (imageUrl.startsWith("http")) return imageUrl;
  try {
    return new URL(imageUrl, baseUrl).href;
  } catch {
    return imageUrl;
  }
}

function extractSource(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}
