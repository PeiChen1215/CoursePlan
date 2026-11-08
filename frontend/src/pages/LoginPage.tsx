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
        <button className="btn w-full" disabled={busy}>
          {busy ? "验证中…" : "进入"}
        </button>
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
