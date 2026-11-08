import { useState } from "react";
import type { BoardTask } from "../hooks/queries";
import { formatMinutes } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

interface Props {
  task: BoardTask;
  readonly: boolean;
  onDone: (taskId: number, minutes: number | null) => void;
  onCorrection: (taskId: number, minutes: number | null) => void;
  onNote: (taskId: number, text: string) => void;
  busy?: boolean;
}

/** 打卡/更正的抽屉内容（外部用 .sheet-pop 定位）。 */
export function TaskCard({ task, readonly, onDone, onCorrection, onNote, busy }: Props) {
  const [minutes, setMinutes] = useState(String(task.minutes));
  const [note, setNote] = useState("");
  const conflict = task.issue_codes.length > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="display text-base">{task.concept_name}</h3>
          <p className="faint num text-xs">
            {task.kind === "study" ? "学习" : "练习"} · {formatMinutes(task.minutes)} ·{" "}
            {task.start.slice(11)}–{task.end.slice(11)}
          </p>
        </div>
        <StatusBadge done={task.done} overdue={task.overdue} conflict={conflict}
                     extra={conflict ? task.issue_codes[0] : undefined} />
      </div>

      <hr className="hairline" />

      {readonly ? (
        <p className="muted text-xs italic">历史版本，只读</p>
      ) : (
        <div className="space-y-3">
          <div className="field-row" style={{ gridTemplateColumns: "5rem 1fr" }}>
            <label htmlFor="actual-minutes">实际用时</label>
            <div className="flex items-baseline gap-2">
              <input
                id="actual-minutes"
                aria-label="实际用时（分钟）"
                className="input num"
                style={{ width: "5rem" }}
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
                inputMode="numeric"
              />
              <span className="faint text-xs">分钟</span>
            </div>
          </div>

          {!task.done ? (
            <button className="btn w-full" disabled={busy}
                    onClick={() => onDone(task.task_id, toMinutes(minutes))}>
              标记完成
            </button>
          ) : (
            <button className="btn w-full" disabled={busy}
                    onClick={() => onCorrection(task.task_id, toMinutes(minutes))}>
              更正用时
            </button>
          )}
          {task.done ? (
            <p className="faint text-xs">重复打卡会被拒绝，改用时请用“更正用时”。</p>
          ) : null}

          <div className="field-row" style={{ gridTemplateColumns: "5rem 1fr" }}>
            <label htmlFor="task-note">备注</label>
            <input
              id="task-note"
              aria-label="备注"
              className="input"
              placeholder="卡在哪、怎么解决的"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </div>
          <button
            className="btn btn-quiet w-full"
            disabled={busy || !note.trim()}
            onClick={() => {
              onNote(task.task_id, note.trim());
              setNote("");
            }}
          >
            记下备注
          </button>
        </div>
      )}
    </div>
  );
}

function toMinutes(value: string): number | null {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.round(n);
}
