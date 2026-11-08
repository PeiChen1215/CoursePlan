import { useState } from "react";
import type { BoardTask } from "../hooks/queries";
import { formatRange, formatMinutes } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

interface Props {
  task: BoardTask;
  readonly: boolean;
  onDone: (taskId: number, minutes: number | null) => void;
  onCorrection: (taskId: number, minutes: number | null) => void;
  onNote: (taskId: number, text: string) => void;
  busy?: boolean;
}

export function TaskCard({ task, readonly, onDone, onCorrection, onNote, busy }: Props) {
  const [editing, setEditing] = useState(false);
  const [minutes, setMinutes] = useState<string>(String(task.minutes));
  const [note, setNote] = useState("");

  const conflict = task.issue_codes.length > 0;
  const needsCorrection = task.done && !readonly;

  return (
    <article
      data-testid={"task-" + task.task_id}
      className="card space-y-2"
    >
      <header className="flex items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-slate-800">{task.concept_name}</h4>
          <p className="text-xs text-slate-500">
            {task.kind === "study" ? "学习" : "练习"} · {formatMinutes(task.minutes)}
          </p>
        </div>
        <StatusBadge
          done={task.done}
          overdue={task.overdue}
          conflict={conflict}
          extra={conflict ? task.issue_codes[0] : undefined}
        />
      </header>

      <p className="text-xs text-slate-500">{formatRange(task.start, task.end)}</p>

      {task.actual_minutes != null ? (
        <p className="text-xs text-slate-500">实际用时 {formatMinutes(task.actual_minutes)}</p>
      ) : null}

      {readonly ? (
        <p className="text-xs italic text-slate-400">历史版本，只读</p>
      ) : (
        <div className="space-y-2">
          {!task.done ? (
            <div className="flex items-center gap-2">
              <input
                aria-label="实际用时（分钟）"
                className="input w-24"
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
                inputMode="numeric"
              />
              <button
                className="btn-primary"
                disabled={busy}
                onClick={() => onDone(task.task_id, toMinutes(minutes))}
              >
                标记完成
              </button>
              <button className="btn-ghost" onClick={() => setEditing((v) => !v)}>
                {editing ? "收起" : "加备注"}
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                className="btn-ghost"
                disabled={busy}
                onClick={() => onCorrection(task.task_id, toMinutes(minutes))}
              >
                更正用时
              </button>
              <button className="btn-ghost" onClick={() => setEditing((v) => !v)}>
                {editing ? "收起" : "加备注"}
              </button>
            </div>
          )}

          {editing ? (
            <div className="flex items-center gap-2">
              <input
                aria-label="备注"
                className="input"
                placeholder="记一句：卡在哪、怎么解决的"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
              <button
                className="btn-ghost"
                disabled={busy || !note.trim()}
                onClick={() => {
                  onNote(task.task_id, note.trim());
                  setNote("");
                  setEditing(false);
                }}
              >
                保存备注
              </button>
            </div>
          ) : null}

          {needsCorrection ? (
            <p className="text-xs text-slate-400">重复打卡会被拒绝，请用“更正用时”。</p>
          ) : null}
        </div>
      )}
    </article>
  );
}

function toMinutes(value: string): number | null {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.round(n);
}
