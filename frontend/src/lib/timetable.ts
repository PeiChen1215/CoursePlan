/** 课表布局与可用时间网格的纯计算（可单测）。 */

export const HOUR_START = 8;
export const HOUR_END = 22;
export const HOUR_SPAN = HOUR_END - HOUR_START;

export interface Slot {
  start: string;
  end: string;
}

export interface Block {
  topPct: number;
  heightPct: number;
  dayIndex: number;
}

export interface HourWindow {
  start: number;
  end: number;
}

/** 一周实际用到的时间窗：按最早开始、最晚结束收窄，两端各留一小时。 */
export function hourWindow(slots: Slot[], minHours = 5, pad = 1): HourWindow {
  if (!slots.length) return { start: HOUR_START, end: HOUR_START + 8 };
  let earliest = 24;
  let latest = 0;
  for (const slot of slots) {
    const start = parseLocal(slot.start);
    const end = parseLocal(slot.end);
    earliest = Math.min(earliest, start.getHours() + start.getMinutes() / 60);
    const endHour = end.getHours() + end.getMinutes() / 60;
    latest = Math.max(latest, endHour === 0 ? 24 : endHour);
  }
  let start = Math.max(HOUR_START, Math.floor(earliest) - pad);
  let end = Math.min(HOUR_END, Math.ceil(latest) + pad);
  if (end - start < minHours) {
    end = Math.min(HOUR_END, start + minHours);
    start = Math.max(HOUR_START, end - minHours);
  }
  return { start, end };
}

export function parseLocal(iso: string): Date {
  // 后端给的是本地时间的 "YYYY-MM-DDTHH:MM"，直接交给 Date 解析会被当成 UTC 之外的值，
  // 这里补秒并显式按本地解析，避免时区偏移把块挪到别的格子。
  const [datePart, timePart = "00:00"] = iso.split("T");
  const [y, m, d] = datePart.split("-").map(Number);
  const [hh, mm] = timePart.split(":").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1, hh ?? 0, mm ?? 0, 0, 0);
}

/** 周一为一周起点。 */
export function weekStartOf(iso: string | Date): Date {
  const base = typeof iso === "string" ? parseLocal(iso) : new Date(iso.getTime());
  const day = (base.getDay() + 6) % 7; // 周一=0
  base.setDate(base.getDate() - day);
  base.setHours(0, 0, 0, 0);
  return base;
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date.getTime());
  next.setDate(next.getDate() + days);
  return next;
}

export function toISODate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export interface DayHeader {
  iso: string;
  label: string;
  dayOfMonth: number;
  isToday: boolean;
}

const WEEKDAY = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export function weekDays(monday: Date, today = new Date()): DayHeader[] {
  const todayISO = toISODate(today);
  return WEEKDAY.map((label, index) => {
    const date = addDays(monday, index);
    return { iso: toISODate(date), label, dayOfMonth: date.getDate(), isToday: toISODate(date) === todayISO };
  });
}

/** 把一个时段换算成课表格里的位置（百分比相对给定的时间窗，默认 08:00–22:00）。 */
export function toBlock(slot: Slot, dayIndex: number, win?: HourWindow): Block {
  const from = win?.start ?? HOUR_START;
  const span = (win?.end ?? HOUR_END) - from;
  const start = parseLocal(slot.start);
  const end = parseLocal(slot.end);
  const startHour = start.getHours() + start.getMinutes() / 60;
  const endHour = end.getHours() + end.getMinutes() / 60;
  const top = clamp01((startHour - from) / span);
  const bottom = clamp01((endHour - from) / span);
  // 最小高度是按“百分比”兜底，不是按比例，否则短任务会被放大成整列
  return { topPct: top * 100, heightPct: Math.max((bottom - top) * 100, 2.2), dayIndex };
}

export function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

/** 某一天的任务负荷（分钟），用于日负荷条。 */
export function dailyMinutes<T extends Slot>(items: T[]): number[] {
  const out = new Array(7).fill(0) as number[];
  for (const item of items) {
    const start = parseLocal(item.start);
    const end = parseLocal(item.end);
    const index = (start.getDay() + 6) % 7;
    out[index] += Math.round((end.getTime() - start.getTime()) / 60000);
  }
  return out;
}

export function maxOf(values: number[]): number {
  return values.reduce((a, b) => Math.max(a, b), 0);
}

/* ---------------- 可用时间网格 ---------------- */

export const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type DayKey = (typeof DAY_KEYS)[number];

export function cellId(day: DayKey, hour: number): string {
  return `${day}-${hour}`;
}

export function rangesToCells(ranges: Record<string, string[][]>): Set<string> {
  const cells = new Set<string>();
  for (const day of DAY_KEYS) {
    for (const [start, end] of ranges[day] ?? []) {
      const from = Number(start.split(":")[0]);
      const to = Number(end.split(":")[0]);
      for (let hour = from; hour < to; hour += 1) {
        if (hour >= HOUR_START && hour < HOUR_END) cells.add(cellId(day, hour));
      }
    }
  }
  return cells;
}

/** 把选中的格子合并成连续区间；跨午夜的格子不合并（单日最多 3 段由界面提示）。 */
export function cellsToRanges(cells: Set<string>): Record<string, string[][]> {
  const out: Record<string, string[][]> = {};
  for (const day of DAY_KEYS) {
    const hours = [...cells]
      .filter((id) => id.startsWith(day + "-"))
      .map((id) => Number(id.split("-")[1]))
      .filter((hour) => Number.isFinite(hour) && hour >= HOUR_START && hour < HOUR_END)
      .sort((a, b) => a - b);
    if (!hours.length) continue;
    const ranges: string[][] = [];
    let start = hours[0];
    let prev = hours[0];
    for (const hour of hours.slice(1)) {
      if (hour === prev + 1) {
        prev = hour;
        continue;
      }
      ranges.push([clock(start), clock(prev + 1)]);
      start = hour;
      prev = hour;
    }
    ranges.push([clock(start), clock(prev + 1)]);
    out[day] = ranges.slice(0, 3);
  }
  return out;
}

function clock(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}
