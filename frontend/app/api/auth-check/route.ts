import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/auth-check — lightweight password validation.
 * Returns 200 if the Bearer token matches DASHBOARD_PASSWORD, 401 otherwise.
 */
export async function GET(req: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) {
    return NextResponse.json({ error: "Not configured" }, { status: 500 });
  }

  const auth = req.headers.get("authorization");
  if (auth === `Bearer ${password}`) {
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}
