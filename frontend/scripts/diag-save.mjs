/** 诊断：点保存约束时到底发了什么、回了什么 */
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:5173";

const run = async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on("request", (req) => {
    if (req.url().includes("/constraint") && req.method() === "PUT") {
      console.log("→ PUT", req.url(), req.postData());
    }
  });
  page.on("response", async (res) => {
    if (res.url().includes("/constraint") && res.request().method() === "PUT") {
      console.log("← ", res.status(), (await res.text()).slice(0, 300));
    }
  });
  page.on("pageerror", (e) => console.log("pageerror:", e.message));

  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1000);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(500);
  }
  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);

  await page.getByRole("button", { name: /整门课/ }).first().click();
  await page.waitForTimeout(400);
  const btn = page.getByRole("button", { name: "保存约束" });
  console.log("保存按钮禁用:", await btn.isDisabled());
  await btn.click();
  await page.waitForTimeout(3000);

  const toasts = await page.locator("[role=status], .toast, [role=alert]").allInnerTexts().catch(() => []);
  console.log("提示:", JSON.stringify(toasts));
  await browser.close();
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
