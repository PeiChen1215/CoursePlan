import { useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { TaskCard } from "../components/TaskCard";
import { TimetableGrid } from "../components/TimetableGrid";
import { IssueList } from "../components/IssueList";
import { StatusBadge } from "../components/StatusBadge";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { useBoard, usePlans, useSubmitEvent } from "../hooks/queries";
import type { BoardTask } from "../hooks/queries";
import { formatMinutes } from "../lib/format";
import { addDays, toISODate, weekStartOf } from "../lib/timetable";

function todayISO(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
}

function TodayList({ tasks, onSelect }: {
  tasks: BoardTask[]; onSelect: (task: BoardTask) => void;
}) {
  const iso = todayISO();
  const mine = tasks.filter((task) => task.start.startsWith(iso));
  const pending = mine.filter((task) => !task.done);
  const totalMinutes = pending.reduce((sum, task) => sum + task.minutes, 0);

  if (!mine.length) {
    return (
      <p className="empty">
        今天（{iso}）没有排任务。切到「全部」看看后面几天，或者去「调整」重排。
      </p>
    );
  }
  return (
    <section className="sheet sheet-pad">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="display text-sm">今天要做的事（{iso}）</h3>
        <span className="faint text-xs">
          还剩 <span className="num">{pending.length}</span> 个任务，
          约 <span className="num">{formatMinutes(totalMinutes)}</span>
        </span>
      </div>
      <ul className="mt-3">
        {mine.map((task) => (
          <li key={task.task_id + task.start} className="border-b py-2" style={{ borderColor: "var(--rule)" }}>
            <button className="flex w-full items-baseline gap-3 text-left" onClick={() => onSelect(task)}>
              <span className="num faint text-xs" style={{ width: "5.5rem" }}>
                {task.start.slice(11)}–{task.end.slice(11)}
              </span>
              <span className="text-sm">
                {task.concept_name}
                <span className="faint"> · {task.kind === "study" ? "学习" : "练习"}</span>
              </span>
              <span className="num faint ml-auto text-xs">{formatMinutes(task.minutes)}</span>
              <StatusBadge done={task.done} overdue={task.overdue}
                           conflict={task.issue_codes.length > 0} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AllList({ tasks, onSelect }: {
  tasks: BoardTask[]; onSelect: (task: BoardTask) => void;
}) {
  const groups = new Map<string, BoardTask[]>();
  for (const task of tasks) {
    const day = task.start.slice(0, 10);
    groups.set(day, [...(groups.get(day) ?? []), task]);
  }
  return (
    <section className="sheet sheet-pad">
      <h3 className="display text-sm">全周期（{groups.size} 天，{tasks.length} 个任务）</h3>
      <div className="mt-3 space-y-4">
        {[...groups.entries()].map(([day, list]) => (
          <div key={day}>
            <p className="num text-xs" style={{ color: "var(--ink-2)" }}>
              {day}
              <span className="faint"> · {formatMinutes(list.reduce((s, t) => s + t.minutes, 0))}</span>
            </p>
            <ul className="mt-1">
              {list.map((task) => (
                <li key={task.task_id + task.start}
                    className="border-b py-1.5" style={{ borderColor: "var(--rule)" }}>
                  <button className="flex w-full items-baseline gap-3 text-left" onClick={() => onSelect(task)}>
                    <span className="num faint text-xs" style={{ width: "4.5rem" }}>
                      {task.start.slice(11)}
                    </span>
                    <span className="text-sm">{task.concept_name}</span>
                    <span className="faint text-xs">{task.kind === "study" ? "学习" : "练习"}</span>
                    <span className="num faint ml-auto text-xs">{formatMinutes(task.minutes)}</span>
                    <StatusBadge done={task.done} overdue={task.overdue}
                                 conflict={task.issue_codes.length > 0} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

export function BoardPage() {
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const board = useBoard(plan?.plan_id ?? null);
  const submit = useSubmitEvent(plan?.plan_id ?? 0);

  const [view, setView] = useState<"today" | "week" | "all">("week");
  const [weekOffset, setWeekOffset] = useState(0);
  const [selected, setSelected] = useState<BoardTask | null>(null);

  const monday = useMemo(() => {
    const tasks = board.data?.tasks ?? [];
    const anchor = tasks.length ? tasks[0].start : toISODate(new Date());
    return addDays(weekStartOf(anchor), weekOffset * 7);
  }, [board.data, weekOffset]);

  const data = board.data;
  const rate = data ? Math.round(data.progress.completion_rate * 100) : 0;
  const overdue = data?.progress.overdue_tasks.length ?? 0;

  function notifyError(err: unknown) {
    toast.push(err instanceof Error ? err.message : String(err), "error");
  }

  return (
    <Layout>
      <div className="space-y-5">
        <section className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="display text-xl">本周课表</h2>
            <p className="faint mt-1 text-xs">
              每格是一小时；块的高度就是任务时长。点块可打卡、更正或写备注。
            </p>
          </div>
          <div className="flex items-baseline gap-4">
            <span className="flex items-baseline gap-2 text-sm">
              {(["today", "week", "all"] as const).map((item) => (
                <button
                  key={item}
                  className="btn-link"
                  style={{
                    borderBottomColor: view === item ? "var(--ink)" : "var(--rule-strong)",
                    color: view === item ? "var(--ink)" : "var(--ink-2)",
                  }}
                  onClick={() => setView(item)}
                >
                  {item === "today" ? "今天" : item === "week" ? "本周" : "全部"}
                </button>
              ))}
            </span>
            {view === "week" ? (
              <span className="flex items-baseline gap-3">
                <button className="btn-link text-sm" onClick={() => setWeekOffset((v) => v - 1)}>
                  上一周
                </button>
                <button className="btn-link text-sm" onClick={() => setWeekOffset(0)}>
                  回到本周
                </button>
                <button className="btn-link text-sm" onClick={() => setWeekOffset((v) => v + 1)}>
                  下一周
                </button>
              </span>
            ) : null}
          </div>
        </section>

        {data ? (
          <section className="flex flex-wrap items-baseline gap-6 text-sm">
            <span>
              完成 <span className="num">{data.progress.done_tasks}</span> /{" "}
              <span className="num">{data.progress.total_tasks}</span>
            </span>
            <span className="muted">
              计划 <span className="num">{formatMinutes(data.progress.planned_minutes)}</span>
            </span>
            <span className="muted">
              实际 <span className="num">{formatMinutes(data.progress.actual_minutes)}</span>
            </span>
            {overdue ? (
              <span style={{ color: "var(--rust)" }}>
                逾期 <span className="num">{overdue}</span> 个任务
              </span>
            ) : null}
            <span className="ml-auto flex items-center gap-2">
              <span className="faint text-xs">完成率</span>
              <span className="num text-lg">{rate}%</span>
            </span>
          </section>
        ) : null}

        {board.error ? <ErrorBox error={board.error} /> : null}

        {plan == null ? (
          <p className="empty">还没有学习计划。先去「填写约束」，填完会自动生成一份草案。</p>
        ) : null}

        {data && data.tasks.length === 0 ? (
          <p className="empty">
            这个版本还没有排入任何任务。回到「填写约束」检查可用时间与截止日期。
          </p>
        ) : null}

        {data && data.tasks.length > 0 && view === "week" ? (
          <TimetableGrid tasks={data.tasks} monday={monday} onSelect={setSelected} />
        ) : null}

        {data && view === "today" ? (
          <TodayList tasks={data.tasks} onSelect={setSelected} />
        ) : null}

        {data && view === "all" ? (
          <AllList tasks={data.tasks} onSelect={setSelected} />
        ) : null}

        {data?.adjust_hint ? (
          <section
            className="sheet sheet-pad"
            style={{ borderColor: "var(--rust)" }}
            role="status"
          >
            <p className="text-sm" style={{ color: "var(--rust)" }}>
              {data.adjust_hint.message}
            </p>
            <p className="faint mt-1 text-xs">
              逾期超过 {data.adjust_hint.threshold_hours} 小时，建议重排一次；
              已完成的记录不会被改动。
            </p>
            <a className="btn mt-3 inline-flex" href="/adjust">
              去调整计划
            </a>
          </section>
        ) : null}

        {data?.unscheduled.length ? (
          <section className="sheet sheet-pad">
            <h3 className="display text-sm">未排入</h3>
            <p className="faint mt-1 text-xs">
              这些任务没找到放得下的时段，需要放宽约束或减少目标。
            </p>
            <ul className="mt-2">
              {data.unscheduled.map((row) => (
                <li key={row.task_id + row.kind} className="issue" data-level="ERROR">
                  <span className="issue-code">{row.concept_name}</span>
                  <span>
                    {row.kind === "study" ? "学习" : "练习"} · {formatMinutes(row.minutes)}
                    <span className="faint">（{row.reason}）</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {data?.issues.length ? (
          <section className="sheet sheet-pad">
            <h3 className="display text-sm">校验提示</h3>
            <div className="mt-2">
              <IssueList issues={data.issues} />
            </div>
          </section>
        ) : null}

        {selected ? (
          <div className="sheet-pop" role="dialog" aria-label="任务操作">
            <div className="mb-2 flex justify-end">
              <button className="btn-link text-xs" onClick={() => setSelected(null)}>
                关闭
              </button>
            </div>
            <TaskCard
              task={selected}
              readonly={data?.readonly ?? false}
              busy={submit.isPending}
              onDone={(taskId, minutes) =>
                submit.mutate({ taskId, type: "done", minutes }, {
                  onSuccess: () => {
                    toast.push("已打卡", "success");
                    setSelected(null);
                  },
                  onError: notifyError,
                })
              }
              onCorrection={(taskId, minutes) =>
                submit.mutate({ taskId, type: "correction", minutes }, {
                  onSuccess: () => {
                    toast.push("已更正用时", "success");
                    setSelected(null);
                  },
                  onError: notifyError,
                })
              }
              onNote={(taskId, text) =>
                submit.mutate({ taskId, type: "note", note: text }, {
                  onSuccess: () => toast.push("备注已记下", "success"),
                  onError: notifyError,
                })
              }
            />
          </div>
        ) : null}
      </div>
    </Layout>
  );
}
