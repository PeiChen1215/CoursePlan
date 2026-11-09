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
  await page.goto("http://127.0.0.1:5173/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await page.locator("button.btn").first().click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "shots/d1-draft-editable.png", fullPage: true });

  await page.goto("http://127.0.0.1:5173/admin", { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(800);
  await page.screenshot({ path: "shots/d2-admin-course.png", fullPage: true });

  await browser.close();
  console.log("done");
};
run().catch((e) => { console.error("fail:", e.message); process.exit(1); });
