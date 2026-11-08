export interface Envelope<T> {
  code: string;
  message: string;
  data: T;
  field?: string | null;
  detail?: unknown;
  request_id: string;
}

export class ApiError extends Error {
  code: string;
  field?: string | null;
  detail?: unknown;
  status: number;

  constructor(message: string, opts: { code: string; field?: string | null; detail?: unknown; status: number }) {
    super(message);
    this.name = "ApiError";
    this.code = opts.code;
    this.field = opts.field ?? null;
    this.detail = opts.detail;
    this.status = opts.status;
  }

  /** 校验类错误（可定位到字段）*/
  get isValidation(): boolean {
    return this.code === "E1001" || this.code === "E1003";
  }
}

const TOKEN_KEY = "studypath.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

const BASE = "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(BASE + path, { ...init, headers });
  const text = await response.text();
  let body: Envelope<T> | null = null;
  try {
    body = text ? (JSON.parse(text) as Envelope<T>) : null;
  } catch {
    throw new ApiError("响应不是合法 JSON", { code: "E9000", status: response.status });
  }
  if (!body) {
    throw new ApiError("空响应", { code: "E9000", status: response.status });
  }
  if (!response.ok || body.code !== "OK") {
    throw new ApiError(body.message || "请求失败", {
      code: body.code,
      field: body.field,
      detail: body.detail,
      status: response.status,
    });
  }
  return body.data;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, payload?: unknown, headers?: Record<string, string>) =>
    request<T>(path, { method: "POST", body: JSON.stringify(payload ?? {}), headers }),
  put: <T>(path: string, payload?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(payload ?? {}) }),
};
