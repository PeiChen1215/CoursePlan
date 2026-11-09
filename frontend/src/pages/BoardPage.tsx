import { useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { TaskCard } from "../components/TaskCard";
import { TimetableGrid } from "../components/TimetableGrid";
import { IssueList } from "../components/IssueList";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { Card, CardHead, EmptyState, Icon, Ring, Segmented, Stat } from "../components/ui";
import { StatusBadge } from "../components/StatusBadge";
import { useBoard, usePlans, useSubmitEvent } from "../hooks/queries";
import type { BoardTask } from "../hooks/queries";
import { formatMinutes } from "../lib/format";
import { addDays, toISODate, weekStartOf } from "../lib/timetable";

function todayISO(): string {
  return toISODate(new Date());
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
  const progress = data?.progress;
  const rate = progress ? progress.completion_rate : 0;
  const today = todayISO();
  const todayTasks = (data?.tasks ?? []).filter((task) => task.start.startsWith(today));
  const todayLeft = todayTasks.filter((task) => !task.done);
  const todayMinutes = todayLeft.reduce((sum, task) => sum + task.minutes, 0);

  function notifyError(err: unknown) {
    toast.push(err instanceof Error ? err.message : String(err), "error");
  }

  function quickDone(task: BoardTask) {
    submit.mutate({ taskId: task.task_id, type: "done", minutes: task.minutes }, {
      onSuccess: () => toast.push("已打卡：" + task.concept_name, "success"),
      onError: notifyError,
    });
  }

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">看板</h1>
          <p className="sub">
            {plan ? plan.course_name : "还没有学习计划"}
            {progress
              ? " · 共 " + progress.total_tasks + " 个任务，已完成 " + progress.done_tasks
              : ""}
          </p>
        </div>
        <div className="page-head-actions">
          <Segmented
            value={view}
            onChange={setView}
            options={[
              { value: "today", label: "今天" },
              { value: "week", label: "本周" },
              { value: "all", label: "全部" },
            ]}
          />
          {view === "week" ? (
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setWeekOffset((v) => v - 1)}>
                上一周
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setWeekOffset(0)}>
                本周
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setWeekOffset((v) => v + 1)}>
                下一周
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <div className="stack">
        <div className="stat-strip">
          <Stat
            label="完成进度"
            value={progress ? progress.done_tasks + " / " + progress.total_tasks : "—"}
            ratio={rate}
          />
          <Stat
            label="计划投入"
            value={progress ? formatMinutes(progress.planned_minutes) : "—"}
          />
          <Stat
            label="实际投入"
            value={progress ? formatMinutes(progress.actual_minutes) : "—"}
          />
          <Stat
            label="今日待办"
            value={todayLeft.length}
            unit={todayMinutes ? " · " + formatMinutes(todayMinutes) : ""}
          />
        </div>

        {board.error ? <ErrorBox error={board.error} /> : null}

        {plan == null ? (
          <EmptyState
            title="还没有学习计划"
            hint="先填写约束（目标、截止日期、可用时间），系统会生成第一份草案。"
            action={
              <a className="btn" href="/constraint" style={{ marginTop: 6 }}>
                去填写约束
              </a>
            }
          />
        ) : null}

        {data?.adjust_hint ? (
          <Card className="card-pad" quiet>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <span className="chip" data-tone="danger">
                <Icon name="alert" size={13} />
                进度提醒
              </span>
              <div style={{ flex: 1 }}>
                <p className="h3">{data.adjust_hint.message}</p>
                <p className="sub" style={{ marginTop: 2 }}>
                  逾期超过 {data.adjust_hint.threshold_hours} 小时，建议重排一次；已完成的记录不会被改动。
                </p>
              </div>
              <a className="btn btn-ghost btn-sm" href="/adjust">去调整</a>
            </div>
          </Card>
        ) : null}

        <Card>
            <CardHead
              title={view === "today" ? "今天" : view === "all" ? "全周期" : "本周课表"}
              hint={
                view === "week"
                  ? "块的高度就是时长，点击可打卡、更正或看资料"
                  : view === "today"
                    ? "今天要做的事，勾掉即打卡"
                    : "按日期列出全部任务"
              }
            />
            <div className="card-body" style={{ paddingTop: 10 }}>
              {data && data.tasks.length === 0 ? (
                <EmptyState
                  title="这个版本还没有排入任务"
                  hint="回到填写约束，检查可用时间与截止日期后重新生成。"
                />
              ) : null}

              {data && data.tasks.length > 0 && view === "week" ? (
                <TimetableGrid tasks={data.tasks} monday={monday} onSelect={setSelected} />
              ) : null}

              {data && view === "today" ? (
                <TodayList tasks={todayTasks} onSelect={setSelected} />
              ) : null}

              {data && view === "all" ? (
                <AllList tasks={data.tasks} onSelect={setSelected} />
              ) : null}
            </div>
          </Card>

        <div className="grid-3">
            <Card className="card-pad">
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <Ring percent={rate * 100} caption="完成率" />
                <div style={{ minWidth: 0 }}>
                  <p className="h3">整体节奏</p>
                  <p className="sub" style={{ marginTop: 4 }}>
                    已完成 {progress?.done_tasks ?? 0} 个，还有{" "}
                    {(progress?.total_tasks ?? 0) - (progress?.done_tasks ?? 0)} 个。
                  </p>
                  <p className="sub">
                    计划 {progress ? formatMinutes(progress.planned_minutes) : "—"}，
                    实际 {progress ? formatMinutes(progress.actual_minutes) : "—"}。
                  </p>
                </div>
              </div>
            </Card>

            <Card>
              <CardHead
                title="今天"
                hint={today}
                action={
                  <span className="chip" data-tone="brand">
                    {todayLeft.length} 项待做
                  </span>
                }
              />
              <div className="card-body" style={{ paddingTop: 4 }}>
                {todayTasks.length === 0 ? (
                  <p className="sub" style={{ padding: "8px 0" }}>
                    今天没有排任务，可以提前看看「全部」里的后续安排。
                  </p>
                ) : (
                  todayTasks.map((task) => (
                    <div key={task.task_id + task.start} className="row-item">
                      <button
                        className="check-round"
                        data-done={task.done}
                        aria-label={task.done ? "已完成" : "标记完成"}
                        disabled={task.done || submit.isPending}
                        onClick={() => quickDone(task)}
                      >
                        {task.done ? <Icon name="check" size={11} /> : null}
                      </button>
                      <button
                        style={{
                          flex: 1, minWidth: 0, textAlign: "left",
                          background: "none", border: 0, padding: 0, cursor: "pointer",
                        }}
                        onClick={() => setSelected(task)}
                      >
                        <p
                          className="row-title"
                          style={{ textDecoration: task.done ? "line-through" : "none" }}
                        >
                          {task.concept_name}
                        </p>
                        <p className="row-sub num">
                          {task.start.slice(11)}–{task.end.slice(11)} · {formatMinutes(task.minutes)}
                        </p>
                      </button>
                      <span className="chip" data-tone={task.kind === "study" ? "study" : "practice"}>
                        {task.kind === "study" ? "学习" : "练习"}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </Card>

            {data?.unscheduled.length ? (
              <Card>
                <CardHead
                  title="未排入"
                  hint="这些任务没找到放得下的时段"
                  action={<span className="chip" data-tone="danger">{data.unscheduled.length}</span>}
                />
                <div className="card-body" style={{ paddingTop: 4 }}>
                  {data.unscheduled.map((row) => (
                    <div key={row.task_id + row.kind} className="row-item">
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p className="row-title">{row.concept_name}</p>
                        <p className="row-sub">
                          {row.kind === "study" ? "学习" : "练习"} · {formatMinutes(row.minutes)} · {row.reason}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ) : null}

            {data?.issues.length ? (
              <Card>
                <CardHead title="校验提示" action={<span className="chip">{data.issues.length}</span>} />
                <div className="card-body" style={{ paddingTop: 4 }}>
                  <IssueList issues={data.issues} />
                </div>
              </Card>
            ) : null}
          </div>
      </div>

      {selected ? (
        <div className="pop">
          <div className="pop-head">
            <div>
              <p className="h3">{selected.concept_name}</p>
              <p className="row-sub num">
                {selected.start.slice(11)}–{selected.end.slice(11)} · {formatMinutes(selected.minutes)}
              </p>
            </div>
            <button className="btn btn-quiet btn-sm" onClick={() => setSelected(null)} aria-label="关闭">
              <Icon name="close" size={15} />
            </button>
          </div>
          <div className="pop-body">
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
        </div>
      ) : null}
    </Layout>
  );
}

function TodayList({ tasks, onSelect }: {
  tasks: BoardTask[]; onSelect: (task: BoardTask) => void;
}) {
  if (!tasks.length) {
    return (
      <EmptyState
        title="今天没有排任务"
        hint="可以切到「全部」看看后续安排，或去「调整」重排时间。"
      />
    );
  }
  return (
    <div>
      {tasks.map((task) => (
        <div key={task.task_id + task.start} className="row-item">
          <span className="mono-sm" style={{ width: 96 }}>
            {task.start.slice(11)}–{task.end.slice(11)}
          </span>
          <button
            style={{
              flex: 1, minWidth: 0, textAlign: "left",
              background: "none", border: 0, padding: 0, cursor: "pointer",
            }}
            onClick={() => onSelect(task)}
          >
            <p className="row-title">{task.concept_name}</p>
            <p className="row-sub">
              {task.kind === "study" ? "学习" : "练习"} · {formatMinutes(task.minutes)}
            </p>
          </button>
          <StatusBadge
            done={task.done}
            overdue={task.overdue}
            conflict={task.issue_codes.length > 0}
          />
        </div>
      ))}
    </div>
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
  const today = todayISO();
  return (
    <div>
      {[...groups.entries()].map(([day, list]) => (
        <div key={day} style={{ marginBottom: 18 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "4px 0 8px" }}>
            <span className="h3 num">{day}</span>
            {day === today ? <span className="chip" data-tone="brand">今天</span> : null}
            <span className="mono-sm">
              {list.length} 个 · {formatMinutes(list.reduce((s, t) => s + t.minutes, 0))}
            </span>
          </div>
          {list.map((task) => (
            <div key={task.task_id + task.start} className="row-item">
              <span className="mono-sm" style={{ width: 64 }}>{task.start.slice(11)}</span>
              <button
                style={{
                  flex: 1, minWidth: 0, textAlign: "left",
                  background: "none", border: 0, padding: 0, cursor: "pointer",
                }}
                onClick={() => onSelect(task)}
              >
                <p className="row-title">{task.concept_name}</p>
                <p className="row-sub">
                  {task.kind === "study" ? "学习" : "练习"} · {formatMinutes(task.minutes)}
                </p>
              </button>
              <StatusBadge
                done={task.done}
                overdue={task.overdue}
                conflict={task.issue_codes.length > 0}
              />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
