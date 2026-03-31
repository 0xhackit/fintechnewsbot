import { NextRequest, NextResponse } from "next/server";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";

const FEEDBACK_PATH = "state/feedback.json";
const MAX_SIGNALS = 100;
const MIN_PER_TYPE = 5;
const MAX_RULES = 10;

interface FeedbackSignal {
  title: string;
  category: string;
  tier: string;
  signal: "positive" | "negative";
  reason: string;
  timestamp: string;
}

interface FeedbackState {
  version: number;
  updated_at: string;
  signals: FeedbackSignal[];
  learned_rules: string[];
}

function checkAuth(req: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const auth = req.headers.get("authorization");
  return auth === `Bearer ${password}`;
}

function emptyState(): FeedbackState {
  return { version: 1, updated_at: "", signals: [], learned_rules: [] };
}

async function loadFeedback(): Promise<{ state: FeedbackState; sha: string }> {
  try {
    const file = await getFileFromGitHub(FEEDBACK_PATH);
    return { state: JSON.parse(file.content) as FeedbackState, sha: file.sha };
  } catch {
    // File doesn't exist yet — will be created on first write
    return { state: emptyState(), sha: "" };
  }
}

function trimSignals(signals: FeedbackSignal[]): FeedbackSignal[] {
  if (signals.length <= MAX_SIGNALS) return signals;

  // Keep at least MIN_PER_TYPE of each signal type
  const positive = signals.filter((s) => s.signal === "positive");
  const negative = signals.filter((s) => s.signal === "negative");

  const keepPositive = positive.slice(-Math.max(MIN_PER_TYPE, 1));
  const keepNegative = negative.slice(-Math.max(MIN_PER_TYPE, 1));

  // Fill remaining slots with most recent
  const kept = new Set([...keepPositive, ...keepNegative]);
  const remaining = signals.filter((s) => !kept.has(s));
  const slotsLeft = MAX_SIGNALS - kept.size;
  const extras = remaining.slice(-Math.max(slotsLeft, 0));

  return [...kept, ...extras].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
}

/** GET — return current feedback state */
export async function GET(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const { state } = await loadFeedback();
    return NextResponse.json(state);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Load failed" },
      { status: 500 }
    );
  }
}

/** POST — record a feedback signal */
export async function POST(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as Partial<FeedbackSignal>;

    if (!body.title || !body.signal) {
      return NextResponse.json(
        { error: "Missing title or signal" },
        { status: 400 }
      );
    }

    if (body.signal !== "positive" && body.signal !== "negative") {
      return NextResponse.json(
        { error: "Signal must be 'positive' or 'negative'" },
        { status: 400 }
      );
    }

    const { state, sha } = await loadFeedback();

    const newSignal: FeedbackSignal = {
      title: body.title,
      category: body.category || "other",
      tier: body.tier || "unknown",
      signal: body.signal,
      reason: body.reason || body.signal,
      timestamp: new Date().toISOString(),
    };

    state.signals.push(newSignal);
    state.signals = trimSignals(state.signals);
    state.updated_at = new Date().toISOString();

    const content = JSON.stringify(state, null, 2);

    if (sha) {
      await putFileToGitHub(
        FEEDBACK_PATH,
        content,
        sha,
        `chore: record feedback — ${body.signal} (${body.reason || "signal"})`
      );
    } else {
      // First signal — create the file
      // putFileToGitHub with empty sha creates a new file
      const token = process.env.GITHUB_TOKEN;
      if (!token) throw new Error("Missing GITHUB_TOKEN");

      const resp = await fetch(
        `https://api.github.com/repos/0xhackit/fintechnewsbot/contents/${FEEDBACK_PATH}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: `chore: initialize feedback state`,
            content: Buffer.from(content).toString("base64"),
          }),
        }
      );
      if (!resp.ok) {
        throw new Error(`GitHub create failed: ${resp.status}`);
      }
    }

    return NextResponse.json({ success: true, signal: newSignal });
  } catch (err) {
    console.error("Feedback POST error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Record failed" },
      { status: 500 }
    );
  }
}

/** PUT — update learned_rules */
export async function PUT(req: NextRequest) {
  if (!checkAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await req.json()) as { learned_rules?: string[] };

    if (!Array.isArray(body.learned_rules)) {
      return NextResponse.json(
        { error: "learned_rules must be an array" },
        { status: 400 }
      );
    }

    const rules = body.learned_rules
      .map((r) => String(r).trim().slice(0, 200))
      .filter(Boolean)
      .slice(0, MAX_RULES);

    const { state, sha } = await loadFeedback();
    state.learned_rules = rules;
    state.updated_at = new Date().toISOString();

    const content = JSON.stringify(state, null, 2);

    if (sha) {
      await putFileToGitHub(
        FEEDBACK_PATH,
        content,
        sha,
        `chore: update learned rules (via dashboard)`
      );
    }

    return NextResponse.json({ success: true, learned_rules: rules });
  } catch (err) {
    console.error("Feedback PUT error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Update failed" },
      { status: 500 }
    );
  }
}
