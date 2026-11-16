/** 多计划切换：侧栏课程切换器 */
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
  await page.fill("#username", "bob");
  await page.fill("#password", "Bob12345!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1500);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(400);
  }

  const switcher = page.locator("select[aria-label=切换课程计划]");
  const count = await switcher.count();
  console.log("侧栏切换器:", count ? "存在" : "缺失");
  if (count) {
    console.log("计划选项:", await switcher.locator("option").allInnerTexts());
    const first = await switcher.locator("option").first().getAttribute("value");
    const second = await switcher.locator("option").nth(1).getAttribute("value");
    await page.selectOption("select[aria-label=切换课程计划]", second);
    await page.waitForTimeout(1600);
    const heading = await page.locator(".page-head, .agenda-heading").first().innerText().catch(() => "");
    console.log("切到计划", second, "（原", first, "）→ 标题:", heading.replace(/\n/g, " ").slice(0, 60));
  }

  await page.screenshot({ path: resolve(OUT, "d11-4-21-plan-switcher.png"), fullPage: false });
  await browser.close();
  console.log("页面错误:", errors.length ? errors.join(" | ") : "无");
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
