/**
 * 合并后冒烟：走真实后端与真实模型，覆盖登录 → 引导 → 看板 → 弹层 → 打卡 → 主题 → 各页。
 * 用法：先启动后端 8000 与前端 5173，再 pnpm exec node scripts/smoke.mjs
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:5173";
const OUT = "shots/smoke";
const results = [];
const check = (name, ok, detail = "") => {
  results.push((ok ? "PASS " : "FAIL ") + name + (detail ? "  " + detail : ""));
  return ok;
};

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 940 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.fill("#username", "alice");
  await page.fill("#password", "Passw0rd!");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/board", { timeout: 20000 });
  await page.waitForTimeout(1500);

  const skip = page.getByRole("button", { name: /稍后设置/ }).first();
  check("首次访问出引导", (await skip.count()) === 1);
  if (await skip.count()) {
    await skip.click();
    await page.waitForTimeout(600);
  }

  const agenda = page.locator("article.agenda-item");
  check("今日清单渲染", (await agenda.count()) > 0, (await agenda.count()) + " 条");

  await page.getByRole("button", { name: "本周" }).first().click();
  await page.waitForTimeout(900);
  const blocks = page.locator(".ev");
  check("周课表渲染时间块", (await blocks.count()) > 0, (await blocks.count()) + " 块");
  await page.screenshot({ path: OUT + "/week.png" });

  await blocks.first().click();
  await page.waitForTimeout(700);
  check("任务弹层打开", (await page.locator('[role="dialog"]').count()) === 1);
  check("弹层内焦点", await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"]');
    return !!d && d.contains(document.activeElement);
  }));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  check("Esc 关闭弹层", (await page.locator('[role="dialog"]').count()) === 0);

  await page.getByRole("button", { name: "今天" }).first().click();
  await page.waitForTimeout(700);
  const before = await page.evaluate(() => document.body.innerText.match(/(\d+)\s*\/\s*(\d+)\s*项已完成/)?.[0] ?? "");
  const doneBtn = page.getByRole("button", { name: /完成打卡/ }).first();
  check("今日清单有打卡入口", (await doneBtn.count()) > 0, before);
  if (await doneBtn.count()) {
    await doneBtn.click();
    await page.waitForTimeout(1800);
  }
  const after = await page.evaluate(() => document.body.innerText.match(/(\d+)\s*\/\s*(\d+)\s*项已完成/)?.[0] ?? "");
  check("打卡后进度变化", after !== before, before + " → " + after);
  await page.screenshot({ path: OUT + "/board-today.png" });

  await page.evaluate(() => localStorage.setItem("studypath.appearance", "dark"));
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  check("深色主题持久化",
        (await page.evaluate(() => document.documentElement.dataset.theme)) === "dark");
  await page.screenshot({ path: OUT + "/board-dark.png" });
  await page.evaluate(() => localStorage.setItem("studypath.appearance", "light"));

  // 关键回归：解析方式标识必须在
  await page.goto(BASE + "/constraint", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.fill('input[name="utterance"]', "测试到底该怎么写");
  await page.getByRole("button", { name: "解析" }).click();
  await page.waitForTimeout(4000);
  const bodyText = await page.locator("body").innerText();
  const hasModeChip = /模型解析|规则解析|本地模拟/.test(bodyText);
  check("抽取后显示解析方式", hasModeChip,
        (bodyText.match(/模型解析|规则解析|本地模拟/) ?? ["无"])[0]);
  await page.screenshot({ path: OUT + "/constraint.png", fullPage: true });

  for (const [path, name] of [
    ["/draft", "草案"], ["/adjust", "调整"], ["/timeline", "记录"],
    ["/versions", "版本"],
  ]) {
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const text = await page.locator("body").innerText();
    check(name + " 页可打开", text.length > 80, text.replace(/\n/g, " ").slice(0, 22));
  }

  check("无控制台错误", errors.length === 0, errors.slice(0, 2).join(" | "));

  await browser.close();
  const passed = results.filter((r) => r.startsWith("PASS")).length;
  console.log(results.join("\n"));
  console.log("\n通过 " + passed + " / " + results.length);
  if (passed !== results.length) process.exitCode = 1;
};

run().catch((e) => { console.error("fail:", e.message); process.exit(1); });
