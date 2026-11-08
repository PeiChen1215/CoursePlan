import { describe, expect, it } from "vitest";
import {
  HOUR_END, HOUR_START, cellId, cellsToRanges, dailyMinutes, maxOf, rangesToCells, toBlock,
  toISODate, weekDays, weekStartOf,
} from "./timetable";

describe("weekStartOf", () => {
  it("周中任意一天都归到本周一", () => {
    expect(toISODate(weekStartOf("2026-11-11T19:00"))).toBe("2026-11-09");
  });

  it("周日归到前一个周一", () => {
    expect(toISODate(weekStartOf("2026-11-15T10:00"))).toBe("2026-11-09");
  });
});

describe("weekDays", () => {
  it("给出周一到周日七列并标出今天", () => {
    const monday = new Date(2026, 10, 9);
    const days = weekDays(monday, new Date(2026, 10, 11));
    expect(days.map((d) => d.label)).toEqual(["周一", "周二", "周三", "周四", "周五", "周六", "周日"]);
    expect(days[2].iso).toBe("2026-11-11");
    expect(days.filter((d) => d.isToday).map((d) => d.label)).toEqual(["周三"]);
  });
});

describe("toBlock", () => {
  it("把时段换算成百分比位置", () => {
    const block = toBlock({ start: "2026-11-09T08:00", end: "2026-11-09T15:00" }, 0);
    expect(block.topPct).toBe(0);
    expect(block.heightPct).toBeCloseTo(50, 5);
  });

  it("晚间时段落在下半段", () => {
    const block = toBlock({ start: "2026-11-09T19:00", end: "2026-11-09T21:00" }, 3);
    expect(block.topPct).toBeCloseTo((11 / (HOUR_END - HOUR_START)) * 100, 4);
    expect(block.dayIndex).toBe(3);
  });

  it("超出范围的时段被裁剪，且最小高度不为 0", () => {
    const block = toBlock({ start: "2026-11-09T06:00", end: "2026-11-09T07:00" }, 0);
    expect(block.topPct).toBe(0);
    expect(block.heightPct).toBeGreaterThan(0);
  });
});

describe("dailyMinutes", () => {
  it("按星期聚合分钟数", () => {
    const items = [
      { start: "2026-11-09T19:00", end: "2026-11-09T20:00" },
      { start: "2026-11-09T20:00", end: "2026-11-09T20:30" },
      { start: "2026-11-14T09:00", end: "2026-11-14T10:00" },
    ];
    const minutes = dailyMinutes(items);
    expect(minutes[0]).toBe(90);
    expect(minutes[5]).toBe(60);
    expect(maxOf(minutes)).toBe(90);
  });
});

describe("可用时间网格", () => {
  it("区间转格子", () => {
    const cells = rangesToCells({ mon: [["19:00", "21:00"]] });
    expect([...cells].sort()).toEqual([cellId("mon", 19), cellId("mon", 20)]);
  });

  it("格子合并回区间", () => {
    const cells = new Set([cellId("mon", 19), cellId("mon", 20), cellId("wed", 9)]);
    expect(cellsToRanges(cells)).toEqual({ mon: [["19:00", "21:00"]], wed: [["09:00", "10:00"]] });
  });

  it("不连续的格子拆成两段", () => {
    const cells = new Set([cellId("sat", 9), cellId("sat", 11)]);
    expect(cellsToRanges(cells).sat).toEqual([["09:00", "10:00"], ["11:00", "12:00"]]);
  });

  it("超过三段只保留前三段", () => {
    const cells = new Set([
      cellId("sat", 8), cellId("sat", 9), cellId("sat", 11), cellId("sat", 13),
      cellId("sat", 15), cellId("sat", 17),
    ]);
    expect(cellsToRanges(cells).sat).toHaveLength(3);
  });

  it("范围外的格子被忽略", () => {
    const cells = new Set([cellId("mon", 5), cellId("mon", 23)]);
    expect(rangesToCells({})).toEqual(new Set());
    expect(cellsToRanges(cells)).toEqual({});
    expect(HOUR_START).toBe(8);
  });
});
