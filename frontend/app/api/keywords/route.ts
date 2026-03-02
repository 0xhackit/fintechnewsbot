import { NextRequest, NextResponse } from "next/server";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const auth = req.headers.get("authorization");
  return auth === `Bearer ${password}`;
}

/**
 * GET /api/keywords
 * Returns current keywords array from config.json.
 */
export async function GET(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const file = await getFileFromGitHub("config.json");
    const config = JSON.parse(file.content);

    return NextResponse.json({
      keywords: config.keywords ?? [],
    });
  } catch (err) {
    console.error("Keywords GET error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to fetch keywords" },
      { status: 500 }
    );
  }
}

/**
 * PUT /api/keywords
 * Update keywords array in config.json via GitHub API.
 * Body: { keywords: string[] }
 */
export async function PUT(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as { keywords?: string[] };

    if (!Array.isArray(body.keywords)) {
      return NextResponse.json(
        { error: "keywords must be an array of strings" },
        { status: 400 }
      );
    }

    // Dedupe and trim
    const cleaned = [...new Set(
      body.keywords.map((k) => k.trim()).filter(Boolean)
    )];

    // Fetch current config
    const file = await getFileFromGitHub("config.json");
    const config = JSON.parse(file.content);

    config.keywords = cleaned;

    // Commit updated config
    await putFileToGitHub(
      "config.json",
      JSON.stringify(config, null, 4),
      file.sha,
      "chore: update keywords (via dashboard)"
    );

    return NextResponse.json({ keywords: cleaned });
  } catch (err) {
    console.error("Keywords PUT error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to update keywords" },
      { status: 500 }
    );
  }
}
