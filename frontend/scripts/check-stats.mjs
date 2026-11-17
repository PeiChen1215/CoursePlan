/** 管理端学情截图 */
import { chromium } from "playwright";
import { resolve } from "node:path";

const BASE = "http://127.0.0.1:5173";
const OUT = resolve("..", "docs", "06_用户文档", "images");

const run = async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.25,
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", "admin");
  await page.fill("#password", "Admin123!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1200);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(400);
  }
  await page.goto(BASE + "/assessments", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);

  const selects = page.locator("select");
  console.log("下拉数量:", await selects.count());
  // 学情卡片里的下拉：包含"选择试卷"
  const statsSelect = page.locator("select").filter({ hasText: "选择试卷" }).first();
  console.log("学情下拉存在:", await statsSelect.count());
  const options = await statsSelect.locator("option").allInnerTexts();
  console.log("试卷选项:", options);
  await statsSelect.selectOption({ index: 1 });
  await page.waitForTimeout(1500);

  const cardText = await page.locator(".stat-strip").first().innerText().catch(() => "");
  console.log("统计条:", cardText.replace(/\n/g, " | "));
  const table = await page.locator("table.table").last().innerText().catch(() => "");
  console.log("逐题表:", table.replace(/\n/g, " | ").slice(0, 220));
  await page.screenshot({ path: resolve(OUT, "d11-4-26-paper-stats.png"), fullPage: true });
  await browser.close();
  console.log("页面错误:", errors.length ? errors.join(" | ") : "无");
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
