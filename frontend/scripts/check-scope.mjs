/** 验证「范围」：只学目标（闭包）vs 整门课，并留下插图 */
import { chromium } from "playwright";
import { resolve } from "node:path";

const BASE = "http://127.0.0.1:5173";
const OUT = resolve("..", "docs", "06_用户文档", "images");

const saveConstraint = async (page) => {
  await page.getByRole("button", { name: "保存约束" }).click();
  await page.getByText("约束已保存").first().waitFor({ timeout: 15000 });
  await page.waitForTimeout(500);
};

const generate = async (page) => {
  const gen = page.getByRole("button", { name: /生成草案/ }).first();
  if (await gen.count()) {
    await gen.click();
    await page.waitForTimeout(5200);
  }
};

const coverageText = async (page) =>
  (await page.locator(".sub").filter({ hasText: "本次计划覆盖" }).first().innerText().catch(() => "(未找到)"))
    .replace(/\n/g, " ");

const run = async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.25,
  });
  const page = await context.newPage();

  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1200);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(400);
  }

  // ---------- 1) 只学目标 ----------
  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.getByRole("button", { name: /只学这个目标/ }).first().click();
  await page.waitForTimeout(300);
  await saveConstraint(page);

  await page.goto(BASE + "/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await generate(page);
  console.log("只学目标:", await coverageText(page));
  await page.screenshot({ path: resolve(OUT, "d11-4-15-coverage-single.png"), fullPage: true });

  // ---------- 2) 整门课 ----------
  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  const whole = page.getByRole("button", { name: /整门课/ }).first();
  console.log("按钮:", await whole.innerText());
  await whole.click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(OUT, "d11-4-16-scope-course.png"), fullPage: true });
  await saveConstraint(page);

  await page.goto(BASE + "/draft", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await generate(page);
  console.log("整门课:", await coverageText(page));
  const stats = await page.locator(".stat-strip").first().innerText().catch(() => "");
  console.log("统计:", stats.replace(/\n/g, " "));
  await page.screenshot({ path: resolve(OUT, "d11-4-17-coverage-course.png"), fullPage: true });

  // ---------- 3) 还原为只学目标 ----------
  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.getByRole("button", { name: /只学这个目标/ }).first().click();
  await page.waitForTimeout(300);
  await saveConstraint(page);
  console.log("已还原为只学目标");

  await browser.close();
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
