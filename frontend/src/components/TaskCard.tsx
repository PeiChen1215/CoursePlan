import { useState } from "react";
import type { BoardTask } from "../hooks/queries";
import { useConceptResources } from "../hooks/queries";
import { Icon } from "./ui";

interface Props {
  task: BoardTask;
  readonly: boolean;
  onDone: (taskId: number, minutes: number | null) => void;
  onCorrection: (taskId: number, minutes: number | null) => void;
  onNote: (taskId: number, text: string) => void;
  busy?: boolean;
}

/** 任务操作面板内容（外部用 .pop 定位）。 */
export function TaskCard({ task, readonly, onDone, onCorrection, onNote, busy }: Props) {
  const [minutes, setMinutes] = useState(String(task.minutes));
  const [note, setNote] = useState("");
  const resources = useConceptResources(task.concept_id);
  const links = (resources.data?.items ?? []).filter((item) => item.status === "enabled");
  const conflict = task.issue_codes.length > 0;

  return (
    <div className="stack" style={{ gap: 14 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <span className="chip" data-tone={task.kind === "study" ? "study" : "practice"}>
          {task.kind === "study" ? "学习" : "练习"}
        </span>
        {task.done ? <span className="chip" data-tone="done">已完成</span> : null}
        {task.overdue ? <span className="chip" data-tone="danger">逾期</span> : null}
        {conflict ? <span className="chip" data-tone="warn">{task.issue_codes[0]}</span> : null}
        {task.slice_total > 1 ? (
          <span className="chip">
            第 {task.slice_no} / {task.slice_total} 片
          </span>
        ) : null}
      </div>

      {links.length ? (
        <div>
          <p className="field-hint" style={{ marginBottom: 6 }}>这个知识点的资料</p>
          <div className="stack" style={{ gap: 6 }}>
            {links.map((item) => (
              <a
                key={item.resource_id}
                href={item.url ?? undefined}
                target={item.url ? "_blank" : undefined}
                rel="noreferrer"
                className="row-item"
                style={{ textDecoration: "none", padding: "6px 0", gap: 8 }}
              >
                <span className="chip" data-tone="brand">{item.type_label}</span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span className="row-title" style={{ display: "block" }}>{item.title}</span>
                  <span className="row-sub">{item.read_minutes} 分钟</span>
                </span>
                {item.url ? <Icon name="chevron" size={14} /> : null}
              </a>
            ))}
          </div>
        </div>
      ) : null}

      {readonly ? (
        <p className="sub">历史版本，只读</p>
      ) : (
        <>
          <div className="field">
            <label htmlFor="actual-minutes">实际用时</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                id="actual-minutes"
                aria-label="实际用时（分钟）"
                className="input num"
                style={{ width: 96 }}
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
                inputMode="numeric"
              />
              <span className="row-sub">分钟</span>
            </div>
          </div>

          {!task.done ? (
            <button className="btn btn-block" disabled={busy} onClick={() => onDone(task.task_id, toMinutes(minutes))}>
              <Icon name="check" size={15} />
              标记完成
            </button>
          ) : (
            <>
              <button className="btn btn-block" disabled={busy} onClick={() => onCorrection(task.task_id, toMinutes(minutes))}>
                更正用时
              </button>
              <p className="field-hint">重复打卡会被拒绝，改用时请用「更正用时」。</p>
            </>
          )}

          <div className="field">
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
            className="btn btn-ghost btn-block"
            disabled={busy || !note.trim()}
            onClick={() => {
              onNote(task.task_id, note.trim());
              setNote("");
            }}
          >
            记下备注
          </button>
        </>
      )}
    </div>
  );
}

function toMinutes(value: string): number | null {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.round(n);
}
