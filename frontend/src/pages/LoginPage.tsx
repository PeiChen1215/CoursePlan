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
    <div className="relative z-10 mx-auto flex min-h-screen max-w-md flex-col justify-center px-5">
      <div className="mb-8">
        <h1 className="display text-3xl">学径</h1>
        <p className="muted mt-2 text-sm">
          一门课的知识点排成一条时间线。先定约束，再看课表，边学边打卡。
        </p>
      </div>

      <form className="sheet sheet-pad space-y-4" onSubmit={submit}>
        <div className="field-row">
          <label htmlFor="username">账号</label>
          <input id="username" className="input" value={username} autoComplete="username"
                 onChange={(event) => setUsername(event.target.value)} />
        </div>
        <div className="field-row">
          <label htmlFor="password">口令</label>
          <input id="password" type="password" className="input" value={password}
                 autoComplete="current-password"
                 onChange={(event) => setPassword(event.target.value)} />
        </div>
        <button className="btn w-full" disabled={busy || lockedFor > 0}>
          {lockedFor > 0
            ? "已锁定，" + Math.ceil(lockedFor / 60) + " 分钟内不能登录"
            : busy
              ? "验证中…"
              : "进入"}
        </button>
        {lockedFor > 0 ? (
          <p className="text-xs" style={{ color: "var(--rust)" }}>
            输错次数太多，还剩 {lockedFor} 秒。到期后可重试。
          </p>
        ) : null}
        <p className="faint text-xs">
          账号不存在与口令错误返回同一提示，避免被人试出哪些账号存在。
        </p>
      </form>

      <div className="mt-4">
        <ErrorBox error={error} />
      </div>

      <p className="faint mt-8 text-xs">
        演示账号：学生 alice / Passw0rd! · 管理员 admin / Admin123!
      </p>
    </div>
  );
}
