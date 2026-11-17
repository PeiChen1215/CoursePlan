/** 验证：① 管理员能出题 ② 报告有题干/答案/理由 ③ 双标签页切换后提示重新登录 */
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
  await page.waitForTimeout(1000);
  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(300);
  }
};

const run = async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.25,
  });
  const page = await context.newPage();

  // ① 管理员出题
  await login(page, "admin", "Admin123!");
  await page.goto(BASE + "/assessments", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const conceptSelect = page.locator("select[aria-label=选择知识点]");
  const options = await conceptSelect.locator("option").allInnerTexts();
  const target = options.findIndex((text) => text.includes("UML 类图"));
  await conceptSelect.selectOption({ index: target });
  await page.getByRole("button", { name: "AI 出题" }).click();
  await page.getByText("已生成草稿，请检查后发布").waitFor({ timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(800);
  const draftVisible = await page.getByRole("button", { name: "发布" }).count();
  console.log("管理员出题成功（有发布按钮）:", draftVisible > 0);
  await page.screenshot({ path: resolve(OUT, "d11-4-27-admin-generate.png"), fullPage: true });

  // ② 学生作答后看报告
  await login(page, "bob", "Bob12345!");
  await page.goto(BASE + "/assessments", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "开始作答" }).first().click();
  await page.waitForTimeout(900);
  const radios = page.locator("input[type=radio]:visible");
  for (let i = 0; i < await radios.count(); i += 4) {
    await radios.nth(i).check({ force: true });
  }
  const areas = page.locator("textarea:visible");
  for (let i = 0; i < await areas.count(); i += 1) {
    await areas.nth(i).fill("聚合是整体与部分，部分可以独立存在。");
  }
  await page.getByRole("button", { name: /提交并看报告/ }).click();
  await page.waitForTimeout(6000);
  const reportText = await page.locator(".card").last().innerText().catch(() => "");
  console.log("报告片段:", reportText.replace(/\n/g, " | ").slice(0, 320));
  await page.screenshot({ path: resolve(OUT, "d11-4-28-report-detail.png"), fullPage: true });

  // ③ 双标签页身份错位
  const other = await context.newPage();
  await login(other, "alice", "Passw0rd!");
  await page.waitForTimeout(800);
  console.log("另一标签页登录 alice 后，当前页身份:", await page.locator(".user-card").innerText().catch(() => ""));

  await browser.close();
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
