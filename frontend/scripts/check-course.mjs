/** 验证课程信息在学生端可见：约束页课程卡片 + 草案页提醒 */
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
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1200);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(500);
  }

  const sidebarText = await page.locator(".sidebar-foot").first().innerText();
  console.log("侧栏课程行:", sidebarText.replace(/\n/g, " | "));

  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const courseCard = await page.locator("text=这门课").first().count();
  console.log("课程卡片:", courseCard ? "存在" : "缺失");
  await page.screenshot({ path: resolve(OUT, "d11-4-13-course-card.png"), fullPage: true });

  await page.goto(BASE + "/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const gen = page.getByRole("button", { name: /生成草案/ }).first();
  if (await gen.count()) {
    await gen.click();
    await page.waitForTimeout(5200);
  }
  const chip = await page.locator(".chip").first().innerText().catch(() => "");
  console.log("校验标识:", chip);
  await page.screenshot({ path: resolve(OUT, "d11-4-14-draft-check.png"), fullPage: true });

  await browser.close();
  console.log("页面错误:", errors.length ? errors.join(" | ") : "无");
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
