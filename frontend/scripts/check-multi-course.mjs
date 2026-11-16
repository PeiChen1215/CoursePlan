/** 多课程界面验证：管理端课程库、学生选课、侧栏切换 */
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

  // ---------- 管理端课程库 ----------
  await login(page, "admin", "Admin123!");
  await page.goto(BASE + "/admin", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const options = await page.locator("select[name=course_select] option").allInnerTexts();
  console.log("课程库选项:", options);
  await page.screenshot({ path: resolve(OUT, "d11-4-18-course-library.png"), fullPage: true });

  // 切到第二门课，看知识点是否跟着变
  const second = page.locator("select[name=course_select] option").nth(1);
  const secondValue = await second.getAttribute("value");
  await page.selectOption("select[name=course_select]", secondValue);
  await page.waitForTimeout(1200);
  const rows = await page.locator("table.table tbody tr").count();
  const heading = await page.locator(".page-head .sub").innerText();
  console.log("切换到课程", secondValue, "| 标题:", heading, "| 知识点行数:", rows);
  await page.screenshot({ path: resolve(OUT, "d11-4-19-admin-second-course.png"), fullPage: true });

  // ---------- 学生端：bob 有课程 2 的计划，再建课程 1 的计划 ----------
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await login(page, "bob", "Bob12345!");
  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const courseSelect = await page.locator("select[name=course_pick]").count();
  console.log("学生课程选择器:", courseSelect ? "存在" : "缺失");
  const courseOptions = courseSelect
    ? await page.locator("select[name=course_pick] option").allInnerTexts()
    : [];
  console.log("学生可选课程:", courseOptions);
  await page.screenshot({ path: resolve(OUT, "d11-4-20-student-pick-course.png"), fullPage: true });

  await browser.close();
  console.log("页面错误:", errors.length ? errors.join(" | ") : "无");
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
