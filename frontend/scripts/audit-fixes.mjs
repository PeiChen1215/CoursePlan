import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const results = [];
const check = (name, ok, extra = "") => {
  results.push((ok ? "PASS " : "FAIL ") + name + (extra ? "  " + extra : ""));
};

const run = async () => {
  mkdirSync("shots", { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 940 } });
  const errors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto("http://127.0.0.1:5173/login", { waitUntil: "networkidle" });
  check("登录页有跳过链接", (await page.locator("a.skip-link").count()) === 0);

  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.locator("form button").click();
  await page.waitForURL("**/board", { timeout: 15000 });
  await page.waitForTimeout(1200);

  check("看板有跳过链接", (await page.locator("a.skip-link").count()) === 1);
  await page.screenshot({ path: "shots/g-board.png" });

  // URL 状态
  await page.locator('button[aria-pressed]', { hasText: "今天" }).click();
  await page.waitForTimeout(400);
  check("切换今天写入 URL", page.url().includes("view=today"), page.url());

  // 视图切换用 replace，不写历史；切回本周
  await page.locator('button[aria-pressed]', { hasText: "本周" }).click();
  await page.waitForTimeout(500);
  check("切回本周清掉参数", !page.url().includes("view=today"), page.url());

  // 抽屉：Esc 关闭
  await page.locator(".ev").first().click();
  await page.waitForTimeout(500);
  const dialog = page.locator('[role="dialog"]');
  check("抽屉有 role=dialog", (await dialog.count()) === 1);
  check("抽屉打开后焦点在内", await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"]');
    return !!d && d.contains(document.activeElement);
  }));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  check("Esc 关闭抽屉", (await page.locator('[role="dialog"]').count()) === 0);
  check("关闭后背景可滚动", await page.evaluate(() => document.body.style.overflow !== "hidden"));

  // 表单标签接线
  await page.goto("http://127.0.0.1:5173/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const wired = await page.evaluate(() => {
    const labels = [...document.querySelectorAll("label[for]")];
    const controls = labels.filter((l) => document.getElementById(l.htmlFor));
    return { labels: labels.length, controls: controls.length };
  });
  check("Field 标签都接到了控件", wired.labels > 0 && wired.labels === wired.controls,
        JSON.stringify(wired));

  const pressed = await page.evaluate(() =>
    [...document.querySelectorAll(".avail-cell")].filter((el) => el.hasAttribute("aria-pressed")).length);
  check("可用格子有 aria-pressed", pressed > 0, pressed + " 个");
  await page.screenshot({ path: "shots/g-constraint.png", fullPage: true });

  // 窄屏表格不撑破
  await page.setViewportSize({ width: 900, height: 900 });
  await page.goto("http://127.0.0.1:5173/admin", { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(700);
  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth <= window.innerWidth + 1;
  });
  check("900px 下无横向溢出", overflow);
  await page.screenshot({ path: "shots/g-admin-900.png", fullPage: true });

  check("无控制台错误", errors.length === 0, errors.slice(0, 2).join(" | "));

  await browser.close();
  console.log(results.join("\n"));
};

run().catch((e) => {
  console.error("fail:", e.message);
  process.exit(1);
});
