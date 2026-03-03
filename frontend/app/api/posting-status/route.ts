import { NextRequest, NextResponse } from "next/server";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const auth = req.headers.get("authorization");
  return auth === `Bearer ${password}`;
}

/**
 * GET /api/posting-status
 * Returns current posting toggle state from config.json.
 */
export async function GET(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const file = await getFileFromGitHub("config.json");
    const config = JSON.parse(file.content) as {
      alerts?: {
        post_to_x?: boolean;
        post_to_telegram?: boolean;
        auto_approve?: boolean;
        trade_analysis_x?: boolean;
        trade_analysis_telegram?: boolean;
      };
    };

    return NextResponse.json({
      post_to_x: config.alerts?.post_to_x ?? true,
      post_to_telegram: config.alerts?.post_to_telegram ?? true,
      auto_approve: config.alerts?.auto_approve ?? true,
      trade_analysis_x: config.alerts?.trade_analysis_x ?? false,
      trade_analysis_telegram: config.alerts?.trade_analysis_telegram ?? false,
    });
  } catch (err) {
    console.error("Posting status GET error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to fetch status" },
      { status: 500 }
    );
  }
}

/**
 * PUT /api/posting-status
 * Update posting toggles in config.json via GitHub API.
 */
export async function PUT(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as {
      post_to_x?: boolean;
      post_to_telegram?: boolean;
      trade_analysis_x?: boolean;
      trade_analysis_telegram?: boolean;
    };

    // Fetch current config
    const file = await getFileFromGitHub("config.json");
    const config = JSON.parse(file.content);

    // Update only the fields that were provided
    if (!config.alerts) config.alerts = {};

    if (typeof body.post_to_x === "boolean") {
      config.alerts.post_to_x = body.post_to_x;
    }
    if (typeof body.post_to_telegram === "boolean") {
      config.alerts.post_to_telegram = body.post_to_telegram;
    }
    if (typeof body.trade_analysis_x === "boolean") {
      config.alerts.trade_analysis_x = body.trade_analysis_x;
    }
    if (typeof body.trade_analysis_telegram === "boolean") {
      config.alerts.trade_analysis_telegram = body.trade_analysis_telegram;
    }

    // Commit updated config
    await putFileToGitHub(
      "config.json",
      JSON.stringify(config, null, 4),
      file.sha,
      "chore: toggle posting (via dashboard)"
    );

    return NextResponse.json({
      post_to_x: config.alerts.post_to_x,
      post_to_telegram: config.alerts.post_to_telegram,
      auto_approve: config.alerts.auto_approve,
      trade_analysis_x: config.alerts.trade_analysis_x,
      trade_analysis_telegram: config.alerts.trade_analysis_telegram,
    });
  } catch (err) {
    console.error("Posting status PUT error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to update status" },
      { status: 500 }
    );
  }
}
