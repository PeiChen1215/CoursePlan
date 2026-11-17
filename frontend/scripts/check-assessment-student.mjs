/** 学生端：作答 + 报告截图（试卷已由 API 发布） */
import { chromium } from "playwright";
import { resolve } from "node:path";

const BASE = "http://127.0.0.1:5173";
const OUT = resolve("..", "docs", "06_用户文档", "images");

const login = async (page, user, pwd) => {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", user);
  await page.fill("#password", pwd);
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1200);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(400);
  }
};

const run = async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.25,
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  // 学生端
  await login(page, "alice", "Passw0rd!");
  await page.goto(BASE + "/assessments", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const skipDialog = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skipDialog.count()) {
    await skipDialog.click();
    await page.waitForTimeout(400);
  }
  console.log("列表卡片:", (await page.locator(".card").count()), "| 试卷条目:",
    await page.locator("text=道题").count());
  await page.screenshot({ path: resolve(OUT, "d11-4-23-assessment-list.png"), fullPage: true });

  await page.getByRole("button", { name: "开始作答" }).first().click();
  await page.waitForTimeout(1000);
  const radar = page.locator("input[type=radio]:visible");
  const radioCount = await radar.count();
  console.log("可见单选选项:", radioCount);
  for (let i = 0; i < radioCount; i += 4) {
    await radar.nth(i).check({ force: true });
  }
  const areas = page.locator("textarea:visible");
  for (let i = 0; i < await areas.count(); i += 1) {
    await areas.nth(i).fill("聚合是整体与部分，部分可独立存在；组合的生命周期与整体一致。");
  }
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(OUT, "d11-4-24-take-assessment.png"), fullPage: true });

  const submitBtn = page.getByRole("button", { name: /提交并看报告/ });
  console.log("提交按钮:", await submitBtn.count(), "visible:", await submitBtn.first().isVisible().catch(() => false));
  await page.screenshot({ path: resolve(OUT, "d11-4-24b-before-submit.png"), fullPage: true });
  await submitBtn.first().click({ force: true });
  await page.waitForTimeout(6000);
  const chip = await page.locator(".chip").first().innerText().catch(() => "");
  console.log("得分:", chip);
  const text = await page.locator(".card-body").last().innerText().catch(() => "");
  console.log("报告:", text.replace(/\n/g, " ").slice(0, 240));
  await page.screenshot({ path: resolve(OUT, "d11-4-25-assessment-report.png"), fullPage: true });

  await browser.close();
  console.log("页面错误:", errors.length ? errors.join(" | ") : "无");
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
