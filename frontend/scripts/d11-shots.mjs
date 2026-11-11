/**
 * D11 用户手册插图：一次生成 12 张，输出到 docs/06_用户文档/images/
 * 前置：后端 8000、前端 5173 均在运行；演示库含 22 个任务。
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const BASE = "http://127.0.0.1:5173";
const OUT = resolve("..", "docs", "06_用户文档", "images");
const shots = [];

const shot = async (page, name, fullPage = false) => {
  const path = resolve(OUT, name);
  await page.screenshot({ path, fullPage });
  shots.push(name);
  console.log("  ✓", name);
};

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const errors = [];

  // ---------- 学生视角 ----------
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.25,
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await shot(page, "d11-4-01-login.png");

  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1500);
  await shot(page, "d11-4-02-onboarding.png");

  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(800);
  }
  await shot(page, "d11-4-03-board-today.png");

  await page.getByRole("button", { name: "本周" }).first().click();
  await page.waitForTimeout(1000);
  await shot(page, "d11-4-04-board-week.png");

  await page.evaluate(() => localStorage.setItem("studypath.appearance", "dark"));
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await shot(page, "d11-4-05-board-dark.png");
  await page.evaluate(() => localStorage.setItem("studypath.appearance", "light"));
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(800);

  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await shot(page, "d11-4-06-constraint.png", true);

  await page.goto(BASE + "/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const gen = page.getByRole("button", { name: /生成草案/ }).first();
  if (await gen.count()) {
    await gen.click();
    await page.waitForTimeout(2500);
  }
  await shot(page, "d11-4-07-draft.png", true);

  await page.goto(BASE + "/adjust", { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const replan = page.getByRole("button", { name: /重排并预览/ }).first();
  if (await replan.count()) {
    await replan.click();
    await page.waitForTimeout(3000);
  }
  await shot(page, "d11-4-08-adjust.png", true);

  await page.goto(BASE + "/versions", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await shot(page, "d11-4-09-versions.png");

  await page.goto(BASE + "/timeline", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await shot(page, "d11-4-10-timeline.png");

  // ---------- 管理员视角 ----------
  const logout = page.getByRole("button", { name: /退出/ }).first();
  if (await logout.count()) {
    await logout.click();
    await page.waitForTimeout(800);
  }
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", "admin");
  await page.fill("#password", "Admin123!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1000);
  const guide = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await guide.count()) {
    await guide.click();
    await page.waitForTimeout(500);
  }
  await page.goto(BASE + "/admin", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await shot(page, "d11-4-11-admin.png", true);

  // ---------- 移动端 ----------
  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });
  const mpage = await mobile.newPage();
  await mpage.goto(BASE + "/login", { waitUntil: "networkidle" });
  await mpage.fill("#username", "alice");
  await mpage.fill("#password", "Passw0rd!");
  await mpage.getByRole("button", { name: "登录" }).click();
  await mpage.waitForURL("**/board", { timeout: 20000 });
  await mpage.waitForTimeout(1500);
  const mskip = mpage.getByRole("button", { name: /稍后设置/ }).first();
  if (await mskip.count()) {
    await mskip.click();
    await mpage.waitForTimeout(600);
  }
  await shot(mpage, "d11-4-12-mobile.png");

  await browser.close();
  console.log("\n共 ", shots.length, " 张", errors.length ? "；页面错误: " + errors.join(" | ") : "；无页面错误");
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
