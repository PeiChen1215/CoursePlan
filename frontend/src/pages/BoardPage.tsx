import { useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { TaskCard } from "../components/TaskCard";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { useAuth } from "../hooks/useAuth";
import { useBoard, usePlans, useSubmitEvent } from "../hooks/queries";
import type { BoardTask } from "../hooks/queries";
import { groupTasks, utilizationLabel } from "../lib/format";
import type { GroupMode } from "../lib/format";

export function BoardPage() {
  const { me } = useAuth();
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const [mode, setMode] = useState<GroupMode>("day");
  const [version, setVersion] = useState<number | undefined>(undefined);

  const board = useBoard(plan?.plan_id ?? null, version);
  const submit = useSubmitEvent(plan?.plan_id ?? 0);

  const grouped = useMemo(() => {
    if (!board.data) return new Map<string, BoardTask[]>();
    return groupTasks(board.data.tasks, mode);
  }, [board.data, mode]);

  function notifyError(err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    toast.push(message, "error");
  }

  const data = board.data;
  const rate = data ? Math.round(data.progress.completion_rate * 100) : 0;

  return (
    <Layout>
      <div className="space-y-4">
        <section className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">学习看板</h2>
            <p className="text-xs text-slate-500">
              {data?.readonly ? "历史版本，只读" : "当前版本"} · 完成率 {rate}%
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded border border-slate-300 bg-white p-0.5">
              {(["day", "week"] as GroupMode[]).map((item) => (
                <button
                  key={item}
                  className={"rounded px-2 py-1 text-xs " + (mode === item ? "bg-slate-900 text-white" : "text-slate-600")}
                  onClick={() => setMode(item)}
                >
                  {item === "day" ? "按日" : "按周"}
                </button>
              ))}
            </div>
            {data?.readonly ? (
              <button className="btn-ghost" onClick={() => setVersion(undefined)}>
                回到当前版本
              </button>
            ) : null}
          </div>
        </section>

        {plan == null ? (
          <p className="text-sm text-slate-500">还没有学习计划，请先到「约束」页创建。</p>
        ) : null}

        {board.error ? <ErrorBox error={board.error} /> : null}

        {data ? (
          <>
            <section className="card">
              <div className="flex items-center justify-between text-sm">
                <span>
                  已完成 {data.progress.done_tasks}/{data.progress.total_tasks} ·
                  计划 {Math.round(data.progress.planned_minutes / 60)} 小时
                </span>
                <span className={utilizationLabel(data.progress.completion_rate).tone}>
                  {data.progress.completion_rate > 0.9 ? "收尾阶段" : "进行中"}
                </span>
              </div>
              <div className="mt-2 h-2 w-full rounded bg-slate-200">
                <div className="h-2 rounded bg-emerald-500" style={{ width: rate + "%" }} />
              </div>
              {data.progress.overdue_tasks.length ? (
                <p className="mt-2 text-xs text-amber-700">
                  有 {data.progress.overdue_tasks.length} 个任务已逾期（逾期不改变计划状态）
                </p>
              ) : null}
            </section>

            <div className="space-y-5">
              {[...grouped.entries()].map(([key, tasks]) => (
                <section key={key}>
                  <h3 className="mb-2 text-sm font-medium text-slate-600">{key}</h3>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {tasks.map((task) => (
                      <TaskCard
                        key={task.task_id + "-" + task.start}
                        task={task}
                        readonly={data.readonly}
                        busy={submit.isPending}
                        onDone={(taskId, minutes) =>
                          submit.mutate(
                            { taskId, type: "done", minutes },
                            { onError: notifyError, onSuccess: () => toast.push("已打卡", "success") },
                          )
                        }
                        onCorrection={(taskId, minutes) =>
                          submit.mutate(
                            { taskId, type: "correction", minutes },
                            { onError: notifyError, onSuccess: () => toast.push("已更正用时", "success") },
                          )
                        }
                        onNote={(taskId, text) =>
                          submit.mutate(
                            { taskId, type: "note", note: text },
                            { onError: notifyError, onSuccess: () => toast.push("备注已记录", "success") },
                          )
                        }
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>

            {data.unscheduled.length ? (
              <section className="card">
                <h3 className="text-sm font-semibold text-slate-700">未排入任务</h3>
                <p className="text-xs text-slate-500">这些任务没排进任何时段，需要调整约束或目标。</p>
                <ul className="mt-2 space-y-1 text-sm">
                  {data.unscheduled.map((row) => (
                    <li key={row.task_id + "-" + row.kind} className="flex justify-between">
                      <span>
                        {row.concept_name}（{row.kind === "study" ? "学习" : "练习"}）
                      </span>
                      <span className="text-xs text-rose-600">{row.reason}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {data.issues.length ? (
              <section className="card">
                <h3 className="text-sm font-semibold text-slate-700">校验提示</h3>
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {data.issues.map((issue, index) => (
                    <li key={issue.code + index}>
                      {issue.level} · {issue.code}：{issue.message}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {me?.role === "student" ? (
              <p className="text-xs text-slate-400">
                提示：同一任务重复打卡会被拒绝，改用时请用「更正用时」。
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </Layout>
  );
}
