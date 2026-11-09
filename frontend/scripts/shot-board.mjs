import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const run = async () => {
  mkdirSync("shots", { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto("http://127.0.0.1:5173/login", { waitUntil: "networkidle" });
  await page.screenshot({ path: "shots/v2-login.png" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.locator("form button").click();
  await page.waitForURL("**/board", { timeout: 15000 });
  await page.waitForTimeout(1600);
  await page.screenshot({ path: "shots/v2-board.png" });
  await browser.close();
  console.log("done");
};
run().catch((e) => { console.error("fail:", e.message); process.exit(1); });
