import { describe, expect, it } from "vitest";
import {
  STATUS_STYLES, addDays, formatMinutes, formatRange, groupTasks, isoWeekKey, parseClock,
  pickStatus, summarizeIssues, todayLocalISO, utilizationLabel,
} from "./format";

describe("formatMinutes", () => {
  it("把分钟拆成小时与分钟", () => {
    expect(formatMinutes(90)).toBe("1 小时 30 分");
    expect(formatMinutes(120)).toBe("2 小时");
    expect(formatMinutes(45)).toBe("45 分钟");
  });

  it("非法值返回占位符", () => {
    expect(formatMinutes(Number.NaN)).toBe("—");
  });
});

describe("groupTasks", () => {
  const tasks = [
    { id: "a", start: "2026-11-09T19:00" },
    { id: "b", start: "2026-11-09T20:30" },
    { id: "c", start: "2026-11-11T19:00" },
  ];

  it("按日分组并按时间排序", () => {
    const grouped = groupTasks(tasks, "day");
    expect([...grouped.keys()]).toEqual(["2026-11-09", "2026-11-11"]);
    expect(grouped.get("2026-11-09")?.map((t) => t.id)).toEqual(["a", "b"]);
  });

  it("按周分组", () => {
    const grouped = groupTasks(tasks, "week");
    expect(grouped.size).toBe(1);
  });
});

describe("isoWeekKey", () => {
  it("同一周的日期得到同一个键", () => {
    expect(isoWeekKey("2026-11-09T19:00")).toBe(isoWeekKey("2026-11-15T19:00"));
  });

  it("跨周日期键不同", () => {
    expect(isoWeekKey("2026-11-09T19:00")).not.toBe(isoWeekKey("2026-11-16T19:00"));
  });
});

describe("pickStatus 优先级", () => {
  it("冲突优先于逾期", () => {
    expect(pickStatus({ done: false, overdue: true, conflict: true })).toBe("conflict");
  });

  it("逾期优先于完成", () => {
    expect(pickStatus({ done: true, overdue: true, conflict: false })).toBe("overdue");
  });

  it("默认未开始", () => {
    expect(pickStatus({ done: false, overdue: false, conflict: false })).toBe("pending");
  });

  it("每个状态都有文字与图标（不靠颜色区分）", () => {
    for (const style of Object.values(STATUS_STYLES)) {
      expect(style.label.length).toBeGreaterThan(0);
      expect(style.icon.length).toBeGreaterThan(0);
    }
  });
});

describe("summarizeIssues", () => {
  it("按级别计数", () => {
    const summary = summarizeIssues([{ level: "ERROR" }, { level: "WARN" }, { level: "WARN" }]);
    expect(summary).toEqual({ errors: 1, warns: 2, infos: 0 });
  });
});

describe("utilizationLabel", () => {
  it("按阈值给不同文案", () => {
    expect(utilizationLabel(0.95).text).toBe("很紧张");
    expect(utilizationLabel(0.85).text).toBe("偏紧");
    expect(utilizationLabel(0.6).text).toBe("适中");
    expect(utilizationLabel(0.2).text).toBe("宽松");
  });
});

describe("parseClock", () => {
  it("补零并裁剪越界值", () => {
    expect(parseClock("9:5")).toBe("09:05");
    expect(parseClock("25:99")).toBe("23:59");
    expect(parseClock("abc")).toBe("");
  });
});

describe("日期工具", () => {
  it("addDays 跨月", () => {
    expect(addDays("2026-10-30", 3)).toBe("2026-11-02");
  });

  it("todayLocalISO 形如 YYYY-MM-DD", () => {
    expect(todayLocalISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("formatRange 显示起止时刻", () => {
    const text = formatRange("2026-11-09T19:00", "2026-11-09T21:00");
    expect(text).toContain("19:00");
    expect(text).toContain("21:00");
  });
});
