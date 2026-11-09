import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const run = async () => {
  mkdirSync("shots", { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });
  await page.goto("http://127.0.0.1:5173/login", { waitUntil: "networkidle" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.locator("form button").click();
  await page.waitForURL("**/board", { timeout: 15000 });
  await page.waitForTimeout(1500);

  // 今日视图
  await page.getByText("今天", { exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: "shots/e1-today.png" });

  // 全部视图
  await page.getByText("全部", { exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: "shots/e2-all.png" });

  // 任务抽屉里的资料
  await page.getByText("本周", { exact: true }).click();
  await page.waitForTimeout(800);
  const block = page.locator(".tt-block").first();
  if (await block.count()) {
    await block.click();
    await page.waitForTimeout(900);
    await page.screenshot({ path: "shots/e3-block-resources.png" });
  }

  await page.goto("http://127.0.0.1:5173/admin", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: "shots/e4-admin-resources.png", fullPage: true });
  await browser.close();
  console.log("done");
};
run().catch((e) => { console.error("fail:", e.message); process.exit(1); });
