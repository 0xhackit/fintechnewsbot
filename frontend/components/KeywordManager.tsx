"use client";

import { useState, useEffect, useCallback } from "react";

export default function KeywordManager({ password }: { password: string }) {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [newKeyword, setNewKeyword] = useState("");

  const fetchKeywords = useCallback(async () => {
    try {
      const resp = await fetch("/api/keywords", {
        headers: { Authorization: `Bearer ${password}` },
      });
      if (!resp.ok) throw new Error("Failed to fetch");
      const data = (await resp.json()) as { keywords: string[] };
      setKeywords(data.keywords);
      setError("");
    } catch {
      setError("Failed to load keywords");
    } finally {
      setLoading(false);
    }
  }, [password]);

  useEffect(() => {
    fetchKeywords();
  }, [fetchKeywords]);

  async function saveKeywords(updated: string[]) {
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const resp = await fetch("/api/keywords", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${password}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ keywords: updated }),
      });
      if (!resp.ok) throw new Error("Failed to save");
      const data = (await resp.json()) as { keywords: string[] };
      setKeywords(data.keywords);
      setSuccess("Saved");
      setTimeout(() => setSuccess(""), 2000);
    } catch {
      setError("Failed to save keywords");
    } finally {
      setSaving(false);
    }
  }

  function handleAdd() {
    const kw = newKeyword.trim();
    if (!kw) return;

    const lower = kw.toLowerCase();
    if (keywords.some((k) => k.toLowerCase() === lower)) {
      setError(`"${kw}" already exists`);
      setTimeout(() => setError(""), 2000);
      return;
    }

    const updated = [...keywords, kw];
    setNewKeyword("");
    saveKeywords(updated);
  }

  function handleRemove(keyword: string) {
    const updated = keywords.filter((k) => k !== keyword);
    saveKeywords(updated);
  }

  if (loading) {
    return (
      <div className="controls-card">
        <div className="controls-header">Keyword Tracking</div>
        <p className="controls-loading">Loading keywords...</p>
      </div>
    );
  }

  return (
    <div className="controls-card">
      <div className="controls-header">
        <span>Keyword Tracking</span>
        <span className="kw-count">{keywords.length}</span>
      </div>

      {/* Add keyword input */}
      <div className="kw-add-row">
        <input
          type="text"
          placeholder="Add keyword..."
          value={newKeyword}
          onChange={(e) => setNewKeyword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !saving && handleAdd()}
          className="input kw-input"
          disabled={saving}
        />
        <button
          onClick={handleAdd}
          className="btn btn-primary"
          disabled={saving || !newKeyword.trim()}
        >
          {saving ? "..." : "Add"}
        </button>
      </div>

      {error && <p className="form-error">{error}</p>}
      {success && <p className="kw-success">{success}</p>}

      {/* Keywords list */}
      <div className="kw-tags">
        {keywords.map((kw) => (
          <span key={kw} className="kw-tag">
            {kw}
            <button
              className="kw-remove"
              onClick={() => handleRemove(kw)}
              disabled={saving}
              title={`Remove "${kw}"`}
            >
              &times;
            </button>
          </span>
        ))}
      </div>

      {keywords.length === 0 && (
        <p className="kw-empty">No keywords configured. Add one above to start tracking.</p>
      )}
    </div>
  );
}
