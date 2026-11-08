// 自查截图：登录 → 课表 → 约束 → 草案 → 版本，各存一张到 shots/
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = "http://127.0.0.1:5173";
const OUT = "shots";

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });

  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.screenshot({ path: OUT + "/01-login.png" });

  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.getByRole("button", { name: "进入" }).click();
  await page.waitForURL("**/board", { timeout: 15000 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: OUT + "/02-board.png" });

  // 点一个任务块，看抽屉
  const block = page.locator(".block").first();
  if (await block.count()) {
    await block.click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: OUT + "/03-block-sheet.png" });
    await page.getByRole("button", { name: "关闭" }).click();
  }

  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: OUT + "/04-constraint.png", fullPage: true });

  await page.goto(BASE + "/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: "生成草案" }).click();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: OUT + "/05-draft.png", fullPage: true });

  await page.goto(BASE + "/versions", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: OUT + "/06-versions.png" });

  await browser.close();
  console.log("截图完成：" + OUT);
};

run().catch(async (error) => {
  console.error("截图失败:", error.message);
  process.exit(1);
});
