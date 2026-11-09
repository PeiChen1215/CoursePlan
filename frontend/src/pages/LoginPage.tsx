import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../lib/api";
import { ErrorBox } from "../components/ErrorBox";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("Passw0rd!");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [lockedFor, setLockedFor] = useState(0);

  useEffect(() => {
    if (lockedFor <= 0) return;
    const timer = window.setInterval(() => setLockedFor((v) => Math.max(0, v - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [lockedFor > 0]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/board");
    } catch (err) {
      setError(err);
      if (err instanceof ApiError) {
        const detail = err.detail as { lock_remaining_seconds?: number } | undefined;
        if (detail?.lock_remaining_seconds) setLockedFor(detail.lock_remaining_seconds);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        position: "relative",
        zIndex: 1,
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.05fr) minmax(0, 0.95fr)",
      }}
      className="login-shell"
    >
      <section
        style={{
          padding: "64px 56px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "linear-gradient(160deg, #4338ca 0%, #4f46e5 45%, #7c3aed 100%)",
          color: "#fff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            className="brand-mark"
            style={{ background: "rgba(255,255,255,.18)", boxShadow: "none" }}
          >
            径
          </span>
          <div>
            <div style={{ fontWeight: 650, fontSize: 16 }}>学径</div>
            <div style={{ fontSize: 11, opacity: 0.75, letterSpacing: "0.06em" }}>STUDYPATH</div>
          </div>
        </div>

        <div style={{ maxWidth: 460 }}>
          <h1 style={{ fontSize: 34, lineHeight: 1.25, fontWeight: 650, letterSpacing: "-0.03em", margin: 0 }}>
            把一门课，
            <br />
            排成一条走得完的路。
          </h1>
          <p style={{ marginTop: 16, fontSize: 14, lineHeight: 1.8, opacity: 0.86 }}>
            输入目标与截止日期，系统会按先修关系拆任务、按你的可用时间装箱，
            再全程盯着进度。卡住了会提醒你重排，而不是等到最后一天。
          </p>
          <div style={{ display: "flex", gap: 26, marginTop: 30 }}>
            {[
              ["先修闭包", "不跳步"],
              ["7:3 拆分", "学练配比"],
              ["缓冲 10%", "留余地"],
            ].map(([title, sub]) => (
              <div key={title}>
                <div style={{ fontSize: 15, fontWeight: 600 }}>{title}</div>
                <div style={{ fontSize: 11.5, opacity: 0.7 }}>{sub}</div>
              </div>
            ))}
          </div>
        </div>

        <p style={{ fontSize: 11.5, opacity: 0.6 }}>
          软件工程综合实训 · 第 6 组
        </p>
      </section>

      <section
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px 24px",
        }}
      >
        <div style={{ width: "100%", maxWidth: 360 }}>
          <h2 className="h1" style={{ fontSize: 22 }}>登录</h2>
          <p className="sub" style={{ marginTop: 4, marginBottom: 22 }}>
            用课程账号进入
          </p>

          <form className="stack" style={{ gap: 14 }} onSubmit={submit}>
            <div className="field">
              <label htmlFor="username">账号</label>
              <input
                id="username"
                className="input"
                value={username}
                autoComplete="username"
                onChange={(event) => setUsername(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="password">口令</label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                autoComplete="current-password"
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            <button className="btn btn-block" disabled={busy || lockedFor > 0}>
              {lockedFor > 0
                ? "已锁定，" + Math.ceil(lockedFor / 60) + " 分钟内不能登录"
                : busy
                  ? "验证中…"
                  : "进入"}
            </button>
            {lockedFor > 0 ? (
              <p className="field-hint" style={{ color: "var(--danger)" }}>
                输错次数太多，还剩 {lockedFor} 秒。
              </p>
            ) : null}
          </form>

          <div style={{ marginTop: 16 }}>
            <ErrorBox error={error} />
          </div>

          <p className="field-hint" style={{ marginTop: 22 }}>
            演示账号：学生 alice / Passw0rd! · 管理员 admin / Admin123!
          </p>
        </div>
      </section>
    </div>
  );
}
