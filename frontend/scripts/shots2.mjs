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

  await page.goto("http://127.0.0.1:5173/adjust", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  // 延期到 12-20，再看差异
  const deadline = page.locator("#adj-deadline");
  await deadline.fill("2026-12-20");
  await page.locator("button.btn").first().click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: "shots/a1-adjust-delay.png", fullPage: true });
  await browser.close();
  console.log("done");
};
run().catch((e) => { console.error("fail:", e.message); process.exit(1); });
