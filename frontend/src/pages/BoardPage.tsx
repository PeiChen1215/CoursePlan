import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import { formatClock, formatMinutes } from "../lib/format";
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

  // 视图与周偏移放进 URL：刷新、后退、分享都能回到同一屏
  const [params, setParams] = useSearchParams();
  const rawView = params.get("view");
  const view: "today" | "week" | "all" =
    rawView === "today" || rawView === "all" ? rawView : "week";
  const weekOffset = Number(params.get("week") ?? 0) || 0;

  function setView(next: "today" | "week" | "all") {
    const search = new URLSearchParams(params);
    if (next === "week") search.delete("view");
    else search.set("view", next);
    setParams(search, { replace: true });
  }

  function setWeekOffset(next: number) {
    const search = new URLSearchParams(params);
    if (next === 0) search.delete("week");
    else search.set("week", String(next));
    setParams(search, { replace: true });
  }

  const [selected, setSelected] = useState<BoardTask | null>(null);
  const popRef = useRef<HTMLDivElement>(null);

  // 抽屉：Esc 关闭、焦点进抽屉、关闭后回到原来的块、背景不滚动
  useEffect(() => {
    if (!selected) return;
    const previous = document.activeElement as HTMLElement | null;
    popRef.current?.focus();
    document.body.style.overflow = "hidden";

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSelected(null);
        return;
      }
      if (event.key !== "Tab" || !popRef.current) return;
      const focusable = popRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
      previous?.focus?.();
    };
  }, [selected]);

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
  const now = new Date();
  const localNow = today + "T" + String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0");
  const nextTask = todayLeft.find((task) => task.end > localNow) ?? todayLeft[0];
  const milestones = [...new Set((data?.tasks ?? []).map((task) => task.concept_name))];

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
          <h1 className="h1">学习看板</h1>
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
        </div>
      </header>

      <div className="stack">
        {data && plan ? (
          <section className="learning-overview" aria-label="课程学习概览">
            <div className="overview-main">
              <p className="overview-label"><Icon name="book" />正在学习 <span>v{plan.current_version}</span></p>
              <h2>{plan.course_name}</h2>
              <div className="course-path" aria-label="知识点进度">
                {milestones.map((name, index) => {
                  const tasks = data.tasks.filter((task) => task.concept_name === name);
                  const done = tasks.every((task) => task.done);
                  return <span className="path-step" data-done={done} data-active={name === nextTask?.concept_name} key={name} title={name + (done ? " · 已完成" : " · 待学习")}><i>{done ? <Icon name="check" size={10} /> : String(index + 1).padStart(2, "0")}</i><span>{name}</span></span>;
                })}
              </div>
              <p className="overview-caption">{milestones.length} 个知识点<span>已完成 {progress?.done_tasks ?? 0} 项任务</span></p>
            </div>
            <div className="overview-focus">
              <p className="overview-label"><Icon name="clock" />今日下一步</p>
              <h3>{nextTask ? nextTask.concept_name : "今日任务已完成"}</h3>
              <p>{nextTask ? formatClock(nextTask.start) + " · " + formatMinutes(nextTask.minutes) + " · " + (nextTask.kind === "study" ? "学习" : "练习") : "保持节奏，明天继续。"}</p>
              {nextTask ? <button className="focus-action" onClick={() => setSelected(nextTask)}>查看任务<Icon name="chevron" /></button> : <button className="focus-action" onClick={() => setView("all")}>查看后续安排<Icon name="chevron" /></button>}
            </div>
          </section>
        ) : null}
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
              <Link className="btn" to="/constraint" style={{ marginTop: 6 }}>
                去填写约束
              </Link>
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
              <Link className="btn btn-ghost btn-sm" to="/adjust">去调整</Link>
            </div>
          </Card>
        ) : null}

        <Card>
            <CardHead
              title={view === "today" ? "今日安排" : view === "all" ? "全部任务" : "每周课表"}
              action={view === "week" ? (
                <div className="week-navigation">
                  <span className="week-range">{monday.getMonth() + 1}月{monday.getDate()}日 – {addDays(monday, 6).getMonth() + 1}月{addDays(monday, 6).getDate()}日</span>
                  <button className="btn btn-ghost btn-sm btn-icon icon-prev" title="上一周" aria-label="上一周" onClick={() => setWeekOffset(weekOffset - 1)}><Icon name="chevron" /></button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setWeekOffset(0)}>本周</button>
                  <button className="btn btn-ghost btn-sm btn-icon" title="下一周" aria-label="下一周" onClick={() => setWeekOffset(weekOffset + 1)}><Icon name="chevron" /></button>
                </div>
              ) : null}
            />
            <div className="card-body" style={{ paddingTop: 10 }}>
              {board.isPending && plan ? <div className="skeleton board-loading" role="status" aria-label="正在加载课表" /> : null}
              {data && data.tasks.length === 0 ? (
                <EmptyState
                  title="这个版本还没有排入任务"
                  hint="回到填写约束，检查可用时间与截止日期后重新生成。"
                />
              ) : null}

              {data && data.tasks.length > 0 && view === "week" ? (
                <>
                  <TimetableGrid tasks={data.tasks} monday={monday} onSelect={setSelected} />
                  <div className="legend"><span><i />学习</span><span><i />练习</span><span><i />已完成</span></div>
                </>
              ) : null}

              {data && view === "today" ? (
                <TodayList tasks={todayTasks} onSelect={setSelected} />
              ) : null}

              {data && view === "all" ? (
                <AllList tasks={data.tasks} onSelect={setSelected} />
              ) : null}
            </div>
          </Card>

        <div className="board-summary">
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
                          {formatClock(task.start)}–{formatClock(task.end)} · {formatMinutes(task.minutes)}
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
        <>
        <div className="dialog-backdrop" onClick={() => setSelected(null)} aria-hidden="true" />
        <div
          className="pop"
          role="dialog"
          aria-modal="true"
          aria-label="任务操作"
          tabIndex={-1}
          ref={popRef}
        >
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
        </>
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
            {formatClock(task.start)}–{formatClock(task.end)}
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
              <span className="mono-sm" style={{ width: 64 }}>{formatClock(task.start)}</span>
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
