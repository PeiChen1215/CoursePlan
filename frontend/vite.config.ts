import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 不引入 @types/node：用 globalThis 取进程环境变量
const API_TARGET =
  (
    globalThis as unknown as {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env?.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 后端端口可用 VITE_API_TARGET 覆盖（8000 被占用时便于换端口联调）
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
