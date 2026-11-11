import type { BoardTask } from "../hooks/queries";
import { formatClock } from "../lib/format";
import { dailyMinutes, hourWindow, maxOf, toBlock, weekDays } from "../lib/timetable";
import type { DayHeader } from "../lib/timetable";

interface Props {
  tasks: BoardTask[];
  monday: Date;
  onSelect: (task: BoardTask) => void;
}

const ROW_H = 52;

export function TimetableGrid({ tasks, monday, onSelect }: Props) {
  const days: DayHeader[] = weekDays(monday);
  const weekTasks = tasks.filter((task) => days.some((day) => task.start.startsWith(day.iso)));
  const loads = dailyMinutes(weekTasks);
  const heaviest = maxOf(loads);
  const win = hourWindow(tasks);
  const hours = Array.from({ length: win.end - win.start }, (_, i) => win.start + i);
  const gridHeight = (win.end - win.start) * ROW_H;
  const now = new Date();
  const nowPct =
    (now.getHours() + now.getMinutes() / 60 - win.start) / (win.end - win.start);

  const summary = days
    .map((day) => {
      const count = tasks.filter((task) => task.start.startsWith(day.iso)).length;
      return count ? day.label + " " + count + " 个任务" : null;
    })
    .filter(Boolean)
    .join("，");

  return (
    <div>
      <p className="sr-only">
        本周课表：{summary || "没有任务"}。用 Tab 可逐个查看每个任务块。
      </p>
      <div className="cal-wrap">
      <div
        className="cal"
        role="group"
        aria-label="本周课表"
        style={{ ["--hour-h" as string]: ROW_H + "px" }}
      >
        <div className="cal-head" aria-hidden />
        {days.map((day) => (
          <div key={day.iso} className="cal-head" data-today={day.isToday}>
            <span className="cal-dow">{day.label.replace("周", "")}</span>
            <span className="cal-date num">{day.dayOfMonth}</span>
          </div>
        ))}

        <div className="cal-gutter" style={{ height: gridHeight }}>
          {hours.map((hour) => (
            <span key={hour} className="cal-hour" style={{ top: (hour - win.start) * ROW_H }}>
              {String(hour).padStart(2, "0")}:00
            </span>
          ))}
        </div>

        {days.map((day, index) => {
          const dayTasks = tasks.filter((task) => task.start.startsWith(day.iso));
          return (
            <div
              key={day.iso}
              className="cal-col"
              data-today={day.isToday}
              data-weekend={index >= 5}
              style={{ height: gridHeight }}
            >
              {day.isToday && nowPct > 0 && nowPct < 1 ? (
                <span className="cal-now" style={{ top: nowPct * gridHeight }} aria-hidden />
              ) : null}

              {dayTasks.map((task) => {
                const block = toBlock(task, index, win);
                const pixels = (block.heightPct / 100) * gridHeight;
                const compact = pixels < 42;
                const status = task.done
                  ? "done"
                  : task.overdue
                    ? "overdue"
                    : task.issue_codes.length > 0
                      ? "conflict"
                      : "pending";
                return (
                  <button
                    key={task.task_id + task.start}
                    className="ev"
                    data-kind={task.kind}
                    data-status={status}
                    data-compact={compact}
                    style={{ top: block.topPct + "%", height: block.heightPct + "%" }}
                    onClick={() => onSelect(task)}
                    aria-label={
                      day.label + " " + formatClock(task.start) + " 到 " + formatClock(task.end) +
                      "，" + task.concept_name + "，" +
                      (task.kind === "study" ? "学习" : "练习") + "，" +
                      task.minutes + " 分钟" +
                      (task.done ? "，已完成" : task.overdue ? "，已逾期" : "")
                    }
                    title={
                      task.concept_name + " · " + formatClock(task.start) + "–" + formatClock(task.end)
                    }
                  >
                    <span className="ev-title">
                      {task.concept_name}
                      {task.slice_total > 1 ? (
                        <span style={{ opacity: 0.6, fontWeight: 500 }}>
                          {" "}
                          {task.slice_no}/{task.slice_total}
                        </span>
                      ) : null}
                    </span>
                    {compact ? null : (
                      <span className="ev-meta">
                        {formatClock(task.start)}–{formatClock(task.end)}
                      </span>
                    )}
                    {status === "done" ? <span className="ev-flag">✓</span> : null}
                    {status === "overdue" ? <span className="ev-flag">逾期</span> : null}
                    {status === "conflict" ? <span className="ev-flag">冲突</span> : null}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>

      <div className="load-row">
        <div className="load-cell" />
        {days.map((day, index) => {
          const ratio = heaviest ? loads[index] / heaviest : 0;
          return (
            <div key={day.iso} className="load-cell" data-heavy={ratio > 0.66}>
              <span className="mono-sm">{loads[index] ? loads[index] + " 分" : "—"}</span>
              <div className="load-bar">
                <span style={{ width: Math.round(ratio * 100) + "%" }} />
              </div>
            </div>
          );
        })}
      </div>
      </div>
    </div>
  );
}
