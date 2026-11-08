import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = "http://127.0.0.1:5173";
const OUT = "shots";

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });

  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.locator("form button").click();
  await page.waitForURL("**/board", { timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: OUT + "/s1-board.png" });

  await page.goto(BASE + "/adjust", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await page.screenshot({ path: OUT + "/s2-adjust-empty.png" });
  await page.locator("button.btn").first().click();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: OUT + "/s3-adjust-diff.png", fullPage: true });

  await page.goto(BASE + "/timeline", { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  await page.screenshot({ path: OUT + "/s4-timeline.png" });

  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  await page.screenshot({ path: OUT + "/s5-constraint.png", fullPage: true });

  await browser.close();
  console.log("done");
};

run().catch((error) => {
  console.error("fail:", error.message);
  process.exit(1);
});
