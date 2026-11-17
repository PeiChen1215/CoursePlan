import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, getToken, setToken } from "../lib/api";
import type { LoginResult, Me } from "../lib/types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<LoginResult>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get<Me>("/api/auth/me")
      .then((data) => {
        if (alive) setMe(data);
      })
      .catch(() => {
        setToken(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // 另一个标签页登录/登出时，localStorage 会变；这里同步一次身份，避免
  // "界面显示管理员、请求却用着学生令牌"的错位。
  useEffect(() => {
    const sync = () => {
      const token = getToken();
      if (!token) {
        setMe(null);
        return;
      }
      api.get<Me>("/api/auth/me").then((data) => setMe(data)).catch(() => setMe(null));
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === "studypath.token") sync();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await api.post<LoginResult>("/api/auth/login", { username, password });
    setToken(result.token);
    setMe({ user_id: result.user_id, username, role: result.role });
    return result;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  const value = useMemo(() => ({ me, loading, login, logout }), [me, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
