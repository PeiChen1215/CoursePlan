import type { BoardTask } from "../hooks/queries";
import { pickStatus, STATUS_STYLES } from "../lib/format";
import {
  dailyMinutes, hourWindow, maxOf, toBlock, weekDays,
} from "../lib/timetable";
import type { DayHeader } from "../lib/timetable";

interface Props {
  tasks: BoardTask[];
  monday: Date;
  onSelect: (task: BoardTask) => void;
}

const ROW_H = 46; // 每小时像素高度，同时用于 CSS 变量

export function TimetableGrid({ tasks, monday, onSelect }: Props) {
  const days: DayHeader[] = weekDays(monday);
  const loads = dailyMinutes(tasks);
  const heaviest = maxOf(loads);
  const win = hourWindow(tasks);
  const hours = Array.from({ length: win.end - win.start }, (_, i) => win.start + i);
  const gridHeight = (win.end - win.start) * ROW_H;

  return (
    <div>
      <div className="timetable" style={{ ["--hour-h" as string]: ROW_H + "px" }}>
        <div className="tt-head" aria-hidden />
        {days.map((day) => (
          <div key={day.iso} className="tt-head" data-today={day.isToday}>
            <span className="num">{day.dayOfMonth}</span>
            {day.label}
          </div>
        ))}

        <div className="tt-hours" style={{ height: gridHeight }}>
          {hours.map((hour) => (
            <span key={hour} className="tt-hour-label" style={{ top: (hour - win.start) * ROW_H }}>
              {String(hour).padStart(2, "0")}
            </span>
          ))}
        </div>

        {days.map((day, index) => {
          const dayTasks = tasks.filter((task) => task.start.startsWith(day.iso));
          return (
            <div
              key={day.iso}
              className="tt-col"
              data-today={day.isToday}
              style={{ height: gridHeight }}
            >
              {dayTasks.map((task) => {
                const block = toBlock(task, index, win);
                const pixels = (block.heightPct / 100) * gridHeight;
                const compact = pixels < 38;
                const status = pickStatus({
                  done: task.done, overdue: task.overdue, conflict: task.issue_codes.length > 0,
                });
                return (
                  <button
                    key={task.task_id + task.start}
                    className="block"
                    data-status={status}
                    data-compact={compact}
                    style={{ top: block.topPct + "%", height: block.heightPct + "%" }}
                    onClick={() => onSelect(task)}
                    title={task.concept_name + " · " + task.start.slice(11) + "–" + task.end.slice(11)}
                  >
                    <span className="block-title">
                      {task.concept_name}
                      {task.slice_total > 1 ? (
                        <span className="block-slice"> {task.slice_no}/{task.slice_total}</span>
                      ) : null}
                      {compact ? (
                        <span className="block-kind">{task.kind === "study" ? "学" : "练"}</span>
                      ) : null}
                    </span>
                    {compact ? null : (
                      <span className="block-meta">
                        {task.kind === "study" ? "学" : "练"} {task.start.slice(11)}–{task.end.slice(11)}
                      </span>
                    )}
                    {status === "conflict" ? (
                      <span className="stamp">{STATUS_STYLES.conflict.label}</span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>

      <div className="load-strip" aria-label="每日负荷">
        {days.map((day, index) => (
          <div key={day.iso} className="load-day">
            <span className="faint num text-xs">{loads[index]} 分</span>
            <div
              className="load-bar"
              style={{ width: heaviest ? Math.round((loads[index] / heaviest) * 100) + "%" : "0%" }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
