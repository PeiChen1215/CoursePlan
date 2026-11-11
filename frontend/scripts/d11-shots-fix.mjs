/**
 * 补拍：① 用固定时钟让「今天」有任务；② 重拍草案/调整，等 toast 消失。
 */
import { chromium } from "playwright";
import { resolve } from "node:path";

const BASE = "http://127.0.0.1:5173";
const OUT = resolve("..", "docs", "06_用户文档", "images");

const login = async (page, user, pwd) => {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", user);
  await page.fill("#password", pwd);
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1200);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(600);
  }
};

const run = async () => {
  const browser = await chromium.launch();

  // ---------- 今天（固定到 11-11 20:30，演示库里那天有 3 个任务）----------
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.25,
  });
  const page = await context.newPage();
  try {
    await page.clock.install({ time: new Date("2026-11-11T20:30:00+08:00") });
  } catch (e) {
    console.log("  ! clock 不可用:", e.message);
  }
  await login(page, "alice", "Passw0rd!");
  const dateText = await page.locator(".date-label").first().innerText().catch(() => "");
  const agenda = await page.locator("article.agenda-item").count();
  console.log("  日期显示:", dateText.replace(/\n/g, " "), "｜今日条目:", agenda);
  if (agenda > 0) {
    await page.screenshot({ path: resolve(OUT, "d11-4-03-board-today.png") });
    console.log("  ✓ d11-4-03-board-today.png（有任务）");
  } else {
    console.log("  - 今日仍为空，保留原图");
  }

  // ---------- 草案（等 toast 消失）----------
  await page.goto(BASE + "/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const gen = page.getByRole("button", { name: /生成草案/ }).first();
  if (await gen.count()) {
    await gen.click();
    await page.waitForTimeout(5200);   // toast 3.6s 自动消失
  }
  await page.screenshot({ path: resolve(OUT, "d11-4-07-draft.png"), fullPage: true });
  console.log("  ✓ d11-4-07-draft.png");

  // ---------- 调整（等 toast 消失）----------
  await page.goto(BASE + "/adjust", { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const replan = page.getByRole("button", { name: /重排并预览/ }).first();
  if (await replan.count()) {
    await replan.click();
    await page.waitForTimeout(5600);
  }
  await page.screenshot({ path: resolve(OUT, "d11-4-08-adjust.png"), fullPage: true });
  console.log("  ✓ d11-4-08-adjust.png");

  await browser.close();
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
