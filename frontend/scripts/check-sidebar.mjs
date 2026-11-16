import { chromium } from "playwright";

const BASE = "http://127.0.0.1:5173";

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(2000);

  const text = await page.evaluate(() => document.querySelector(".sidebar-foot")?.textContent ?? "");
  console.log("sidebar textContent:", JSON.stringify(text));

  const plans = await page.evaluate(async () => {
    const response = await fetch("/api/plans", {
      headers: { Authorization: "Bearer " + localStorage.getItem("studypath.token") },
    });
    return response.ok ? await response.json() : { status: response.status };
  });
  console.log("plans[0]:", JSON.stringify(plans?.data?.items?.[0] ?? plans));
  await browser.close();
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
