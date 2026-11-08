export const WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
export const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export function formatMinutes(minutes: number): string {
  if (!Number.isFinite(minutes)) return "—";
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h && m) return `${h} 小时 ${m} 分`;
  if (h) return `${h} 小时`;
  return `${m} 分钟`;
}

export function formatRange(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(s.getMonth() + 1)}-${pad(s.getDate())} ${pad(s.getHours())}:${pad(s.getMinutes())}–${pad(e.getHours())}:${pad(e.getMinutes())}`;
}

export function dayKey(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function isoWeekKey(iso: string): string {
  const d = new Date(iso);
  const target = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNr = (target.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNr + 3);
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
  const diff = target.getTime() - firstThursday.getTime();
  const week = 1 + Math.round(diff / (7 * 24 * 3600 * 1000));
  return `${target.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export type GroupMode = "day" | "week";

export function groupTasks<T extends { start: string }>(items: T[], mode: GroupMode): Map<string, T[]> {
  const out = new Map<string, T[]>();
  const keyOf = mode === "day" ? (s: string) => dayKey(s) : (s: string) => isoWeekKey(s);
  for (const item of items) {
    const key = keyOf(item.start);
    const bucket = out.get(key);
    if (bucket) bucket.push(item);
    else out.set(key, [item]);
  }
  for (const bucket of out.values()) {
    bucket.sort((a, b) => a.start.localeCompare(b.start));
  }
  return new Map([...out.entries()].sort((a, b) => a[0].localeCompare(b[0])));
}

export type TaskStatus = "done" | "overdue" | "conflict" | "pending";

export interface StatusStyle {
  label: string;
  text: string;
  bg: string;
  icon: string;
}

/** 双通道：文字 + 底色，颜色不是唯一区分（D06 §11.6.2）。 */
export const STATUS_STYLES: Record<TaskStatus, StatusStyle> = {
  conflict: { label: "冲突", text: "text-rose-700", bg: "bg-rose-50 border-rose-300", icon: "⚠" },
  overdue: { label: "逾期", text: "text-amber-700", bg: "bg-amber-50 border-amber-300", icon: "!" },
  done: { label: "已完成", text: "text-emerald-700", bg: "bg-emerald-50 border-emerald-300", icon: "✓" },
  pending: { label: "未开始", text: "text-slate-600", bg: "bg-white border-slate-300", icon: "·" },
};

/** 优先级：冲突 > 逾期 > 已完成 > 未开始（D06 §11.6.3）。 */
export function pickStatus(opts: { done: boolean; overdue: boolean; conflict: boolean }): TaskStatus {
  if (opts.conflict) return "conflict";
  if (opts.overdue) return "overdue";
  if (opts.done) return "done";
  return "pending";
}

export function summarizeIssues(issues: { level: string }[]): { errors: number; warns: number; infos: number } {
  return {
    errors: issues.filter((i) => i.level === "ERROR").length,
    warns: issues.filter((i) => i.level === "WARN").length,
    infos: issues.filter((i) => i.level === "INFO").length,
  };
}

export function utilizationLabel(ratio: number): { text: string; tone: string } {
  if (ratio > 0.9) return { text: "很紧张", tone: "text-rose-600" };
  if (ratio > 0.8) return { text: "偏紧", tone: "text-amber-600" };
  if (ratio > 0.5) return { text: "适中", tone: "text-emerald-600" };
  return { text: "宽松", tone: "text-emerald-600" };
}

export function parseClock(value: string): string {
  const m = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!m) return "";
  const hh = Math.min(23, Math.max(0, Number(m[1])));
  const mm = Math.min(59, Math.max(0, Number(m[2])));
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

export function todayLocalISO(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
