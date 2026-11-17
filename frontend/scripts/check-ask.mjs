/** 验证「问一句」：真实模型作答 + 降级两种状态 */
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
  await page.waitForTimeout(1500);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(400);
  }

  const chips = await page.locator(".ask-chip").allInnerTexts();
  console.log("预设问题:", chips);

  await page.locator(".ask-chip").first().click();
  await page.waitForTimeout(6000);
  const answer = await page.locator(".ask-answer p").first().innerText().catch(() => "(无回答)");
  const meta = await page.locator(".ask-meta").first().innerText().catch(() => "");
  console.log("回答:", answer.replace(/\n/g, " ").slice(0, 200));
  console.log("标识:", meta.replace(/\n/g, " | "));
  await page.screenshot({ path: resolve(OUT, "d11-4-22-ask-agent.png"), fullPage: false });

  await browser.close();
  console.log("页面错误:", errors.length ? errors.join(" | ") : "无");
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
