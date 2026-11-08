import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { ErrorBox } from "../components/ErrorBox";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("Passw0rd!");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/board");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm">
      <div className="card space-y-4">
        <div>
          <h2 className="text-lg font-semibold">登录</h2>
          <p className="text-xs text-slate-500">
            账号不存在与口令错误返回同一提示，避免账号被枚举。
          </p>
        </div>
        <form className="space-y-3" onSubmit={submit}>
          <div>
            <label className="label" htmlFor="username">账号</label>
            <input
              id="username"
              className="input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </div>
          <div>
            <label className="label" htmlFor="password">口令</label>
            <input
              id="password"
              type="password"
              className="input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </div>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "登录中…" : "登录"}
          </button>
        </form>
        <ErrorBox error={error} />
      </div>
    </div>
  );
}
