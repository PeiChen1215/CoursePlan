import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, getToken, setToken } from "./api";

const ok = (data: unknown) => ({
  ok: true,
  status: 200,
  text: async () => JSON.stringify({ code: "OK", message: "ok", data, request_id: "r1" }),
});

const fail = (status: number, body: unknown) => ({
  ok: false,
  status,
  text: async () => JSON.stringify(body),
});

describe("api 客户端", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("成功时返回 data", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ok({ hello: 1 })));
    await expect(api.get("/api/x")).resolves.toEqual({ hello: 1 });
  });

  it("失败时抛 ApiError 并带 code/field/detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        fail(400, {
          code: "E1001",
          message: "字段非法",
          data: null,
          field: "deadline",
          detail: { min: 2 },
          request_id: "r2",
        }),
      ),
    );
    await expect(api.get("/api/x")).rejects.toMatchObject({
      code: "E1001",
      field: "deadline",
      status: 400,
    });
  });

  it("非 JSON 响应抛 E9000", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, text: async () => "<html>" })));
    await expect(api.get("/api/x")).rejects.toBeInstanceOf(ApiError);
  });

  it("有令牌时带上 Authorization", async () => {
    setToken("t-123");
    const spy = vi.fn(async () => ok({}));
    vi.stubGlobal("fetch", spy);
    await api.get("/api/x");
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer t-123");
    expect(getToken()).toBe("t-123");
  });

  it("登出后不再带令牌", async () => {
    setToken("t-123");
    setToken(null);
    const spy = vi.fn(async () => ok({}));
    vi.stubGlobal("fetch", spy);
    await api.get("/api/x");
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
  });

  it("post 会序列化 body 并可附加幂等键", async () => {
    const spy = vi.fn(async () => ok({}));
    vi.stubGlobal("fetch", spy);
    await api.post("/api/x", { a: 1 }, { "Idempotency-Key": "k1" });
    const [, init] = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
    expect((init.headers as Headers).get("Idempotency-Key")).toBe("k1");
  });
});
