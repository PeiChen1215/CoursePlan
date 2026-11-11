import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../lib/api";
import { ErrorBox } from "../components/ErrorBox";
import { Icon } from "../components/ui";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("Passw0rd!");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [lockedFor, setLockedFor] = useState(0);
  const locked = lockedFor > 0;

  useEffect(() => {
    if (!locked) return;
    const timer = window.setInterval(() => setLockedFor((v) => Math.max(0, v - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [locked]);

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
    <main className="login-shell">
      <header className="login-brand brand">
        <span className="brand-mark">径</span>
        <div><div className="brand-name">学径</div><div className="brand-sub">StudyPath</div></div>
      </header>
      <section className="login-content" aria-labelledby="login-title">
        <span className="login-symbol"><Icon name="book" size={28} /></span>
        <p className="login-eyebrow">STUDYPATH</p>
        <h1 id="login-title">欢迎回到学径</h1>
        <p className="sub">从今天开始，走好学习的每一步。</p>
        <form className="stack login-form" onSubmit={submit}>
          <div className="field">
            <label htmlFor="username">课程账号</label>
            <input id="username" name="username" className="input" value={username}
              autoComplete="username" autoCapitalize="none" spellCheck={false} required
              onChange={(event) => setUsername(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="password">密码</label>
            <div className="password-control">
              <input id="password" name="password" type={showPassword ? "text" : "password"}
                className="input" value={password} autoComplete="current-password" required
                onChange={(event) => setPassword(event.target.value)} />
              <button type="button" className="password-toggle" aria-label={showPassword ? "隐藏密码" : "显示密码"}
                title={showPassword ? "隐藏密码" : "显示密码"} aria-pressed={showPassword}
                onClick={() => setShowPassword((value) => !value)}><Icon name={showPassword ? "eyeOff" : "eye"} size={18} /></button>
            </div>
          </div>
          <ErrorBox error={error} />
          <button className="btn btn-block login-submit" disabled={busy || locked}>
            {locked ? "请等待 " + lockedFor + " 秒" : busy ? "登录中…" : "登录"}
            {!busy && !locked ? <Icon name="chevron" /> : null}
          </button>
          {locked ? <p role="status" className="field-hint">登录暂时锁定，{lockedFor} 秒后可重试。</p> : null}
        </form>
        <details className="demo-accounts">
          <summary>演示账号</summary>
          <p>学生：alice / Passw0rd!</p><p>管理员：admin / Admin123!</p>
        </details>
      </section>
      <footer className="login-footer">学径 StudyPath <span>课程学习规划</span></footer>
    </main>
  );
}
