import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const run = async () => {
  mkdirSync("shots", { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 940 } });
  await page.goto("http://127.0.0.1:5173/login", { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await page.screenshot({ path: "shots/f-login.png" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.locator("form button").click();
  await page.waitForURL("**/board", { timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "shots/f-board.png" });

  await page.goto("http://127.0.0.1:5173/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: "shots/f-constraint.png", fullPage: true });

  await page.goto("http://127.0.0.1:5173/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const gen = page.locator("button.btn", { hasText: "生成草案" }).first();
  if (await gen.count()) {
    await gen.click();
  }
  await page.waitForTimeout(1800);
  await page.screenshot({ path: "shots/f-draft.png", fullPage: true });

  await page.goto("http://127.0.0.1:5173/versions", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: "shots/f-versions.png" });

  await page.goto("http://127.0.0.1:5173/timeline", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: "shots/f-timeline.png" });

  await page.goto("http://127.0.0.1:5173/adjust", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: "shots/f-adjust.png", fullPage: true });

  await browser.close();
  console.log("done");
};
run().catch((e) => { console.error("fail:", e.message); process.exit(1); });
