/**
 * GitHub Contents API helpers.
 * Used for feed persistence (out/feed.json) and posting toggle updates (config.json).
 */

const REPO = "0xhackit/fintechnewsbot";
const API_BASE = `https://api.github.com/repos/${REPO}/contents`;

interface GitHubFileResult {
  content: string;
  sha: string;
}

/**
 * Fetch a file from GitHub and decode its base64 content.
 */
export async function getFileFromGitHub(
  path: string
): Promise<GitHubFileResult> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error("Missing GITHUB_TOKEN");

  const resp = await fetch(`${API_BASE}/${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github.v3+json",
    },
    cache: "no-store",
  });

  if (!resp.ok) {
    throw new Error(`GitHub GET ${path} failed: ${resp.status}`);
  }

  const data = (await resp.json()) as {
    content?: string;
    sha?: string;
  };

  if (!data.content || !data.sha) {
    throw new Error(`GitHub GET ${path}: missing content or sha`);
  }

  // GitHub returns base64-encoded content with newlines
  const decoded = Buffer.from(data.content.replace(/\n/g, ""), "base64").toString("utf-8");
  return { content: decoded, sha: data.sha };
}

/**
 * Create or update a file on GitHub via the Contents API.
 * Retries once on 409 conflict (concurrent edit).
 */
export async function putFileToGitHub(
  path: string,
  content: string,
  sha: string,
  message: string
): Promise<void> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error("Missing GITHUB_TOKEN");

  const body = {
    message,
    content: Buffer.from(content).toString("base64"),
    sha,
  };

  const resp = await fetch(`${API_BASE}/${path}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github.v3+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (resp.status === 409) {
    // Conflict — refetch SHA and retry once
    const fresh = await getFileFromGitHub(path);
    const retryBody = {
      message,
      content: Buffer.from(content).toString("base64"),
      sha: fresh.sha,
    };

    const retryResp = await fetch(`${API_BASE}/${path}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(retryBody),
    });

    if (!retryResp.ok) {
      throw new Error(`GitHub PUT ${path} retry failed: ${retryResp.status}`);
    }
    return;
  }

  if (!resp.ok) {
    throw new Error(`GitHub PUT ${path} failed: ${resp.status}`);
  }
}
