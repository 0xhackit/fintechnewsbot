"use client";

import { useState } from "react";
import DashboardForm from "./DashboardForm";
import ReviewQueue from "./ReviewQueue";

type Tab = "review" | "post";

export default function AdminPanel() {
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("review");

  async function handleLogin() {
    if (!password.trim()) return;
    try {
      const resp = await fetch("/api/auth-check", {
        headers: { Authorization: `Bearer ${password}` },
      });
      if (resp.ok) {
        setAuthed(true);
        setError("");
      } else {
        setError("Invalid password");
      }
    } catch {
      setError("Connection error");
    }
  }

  if (!authed) {
    return (
      <div className="admin-gate">
        <p className="admin-gate-label">Admin — enter dashboard password</p>
        <div className="admin-gate-row">
          <input
            type="password"
            placeholder="Dashboard password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
          />
          <button onClick={handleLogin}>Enter</button>
        </div>
        {error ? <p className="admin-gate-err">{error}</p> : null}
        <style>{`
          .admin-gate { max-width: 420px; margin: 40px auto; background:#fff; border:1px solid #eff3f4; border-radius:16px; padding:24px; }
          .admin-gate-label { font-size:14px; font-weight:700; color:#0f1419; margin-bottom:12px; }
          .admin-gate-row { display:flex; gap:8px; }
          .admin-gate-row input { flex:1; padding:9px 12px; border:1px solid #cfd9de; border-radius:10px; font-size:14px; }
          .admin-gate-row button { border:none; background:#1d9bf0; color:#fff; font-weight:700; padding:9px 18px; border-radius:10px; cursor:pointer; }
          .admin-gate-err { color:#c81e1e; font-size:13px; margin-top:8px; }
        `}</style>
      </div>
    );
  }

  return (
    <div>
      <div className="admin-tabbar">
        <button className={`admin-tabbtn ${tab === "review" ? "active" : ""}`} onClick={() => setTab("review")}>
          Review queue
        </button>
        <button className={`admin-tabbtn ${tab === "post" ? "active" : ""}`} onClick={() => setTab("post")}>
          Manual post
        </button>
      </div>
      {tab === "review" ? (
        <ReviewQueue password={password} />
      ) : (
        <DashboardForm preAuthed presetPassword={password} />
      )}
      <style>{`
        .admin-tabbar { display:flex; gap:6px; justify-content:center; margin:8px 0 4px; }
        .admin-tabbtn { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:14px; font-weight:700; padding:8px 18px; border-radius:999px; cursor:pointer; }
        .admin-tabbtn:hover { background:rgba(29,155,240,0.08); }
        .admin-tabbtn.active { background:#0f1419; color:#fff; border-color:#0f1419; }
      `}</style>
    </div>
  );
}
