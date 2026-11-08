import type { BoardTask } from "../hooks/queries";
import { pickStatus, STATUS_STYLES } from "../lib/format";
import {
  HOUR_END, HOUR_START, dailyMinutes, maxOf, toBlock, weekDays,
} from "../lib/timetable";
import type { DayHeader } from "../lib/timetable";

interface Props {
  tasks: BoardTask[];
  monday: Date;
  onSelect: (task: BoardTask) => void;
}

const HOURS = Array.from({ length: HOUR_END - HOUR_START + 1 }, (_, i) => HOUR_START + i);
const ROW_H = 44; // 每小时像素高度，同时用于 CSS 变量

export function TimetableGrid({ tasks, monday, onSelect }: Props) {
  const days: DayHeader[] = weekDays(monday);
  const loads = dailyMinutes(tasks);
  const heaviest = maxOf(loads);

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

        <div className="tt-hours" style={{ height: (HOUR_END - HOUR_START) * ROW_H }}>
          {HOURS.map((hour) => (
            <span key={hour} className="tt-hour-label" style={{ top: (hour - HOUR_START) * ROW_H }}>
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
              style={{ height: (HOUR_END - HOUR_START) * ROW_H }}
            >
              {dayTasks.map((task) => {
                const block = toBlock(task, index);
                const status = pickStatus({
                  done: task.done, overdue: task.overdue, conflict: task.issue_codes.length > 0,
                });
                return (
                  <button
                    key={task.task_id + task.start}
                    className="block"
                    data-status={status}
                    style={{ top: block.topPct + "%", height: block.heightPct + "%" }}
                    onClick={() => onSelect(task)}
                    title={task.concept_name + " · " + task.start.slice(11) + "–" + task.end.slice(11)}
                  >
                    <span className="block-title">{task.concept_name}</span>
                    <span className="block-meta">
                      {task.start.slice(11)}–{task.end.slice(11)}
                    </span>
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
