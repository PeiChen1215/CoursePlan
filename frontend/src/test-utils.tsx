import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";

/** 组件测试统一入口：给需要查询的组件套上 QueryClient，并让 fetch 返回空列表。 */
export function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 0 } },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify({ code: "OK", message: "ok", data: { items: [] }, request_id: "t" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}
