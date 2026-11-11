import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Layout } from "../components/Layout";
import { TaskCard } from "../components/TaskCard";
import { TimetableGrid } from "../components/TimetableGrid";
import { IssueList } from "../components/IssueList";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { EmptyState, Icon, Segmented } from "../components/ui";
import { StatusBadge } from "../components/StatusBadge";
import { useBoard, useConstraint, usePlans, useSubmitEvent } from "../hooks/queries";
import type { BoardTask } from "../hooks/queries";
import { formatClock, formatMinutes } from "../lib/format";
import { addDays, toISODate, weekStartOf } from "../lib/timetable";
import { BOARD_VIEW_KEY, readBoardView, savePreference } from "../lib/preferences";
import type { BoardView } from "../lib/preferences";

function todayISO(): string {
  return toISODate(new Date());
}


export function BoardPage() {
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const board = useBoard(plan?.plan_id ?? null);
  const submit = useSubmitEvent(plan?.plan_id ?? 0);
  const constraint = useConstraint(plan?.plan_id ?? null);

  // 视图与周偏移放进 URL：刷新、后退、分享都能回到同一屏
  const [params, setParams] = useSearchParams();
  const [preferredView, setPreferredView] = useState<BoardView>(readBoardView);
  const rawView = params.get("view");
  const view: BoardView = rawView === "today" || rawView === "week" || rawView === "all" ? rawView : preferredView;
  const weekOffset = Number(params.get("week") ?? 0) || 0;

  function setView(next: "today" | "week" | "all") {
    setPreferredView(next);
    savePreference(BOARD_VIEW_KEY, next);
    const search = new URLSearchParams(params);
    if (next === "today") search.delete("view");
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
      <div className="board-layout">
        <div className="board-feed">
          <header className="page-head board-head">
            <div><h1 className="h1">学习</h1><p className="sub">{plan?.course_name ?? "我的学习计划"}</p></div>
            <Link className="btn btn-quiet btn-icon" title="学习偏好" aria-label="学习偏好" to="/constraint"><Icon name="sliders" size={21} /></Link>
          </header>
          <div className="board-tabs">
            <Segmented value={view} onChange={setView} options={[
              { value: "today", label: "今天" }, { value: "week", label: "本周" }, { value: "all", label: "全部任务" },
            ]} />
          </div>

          {plans.error || board.error ? <ErrorBox error={plans.error ?? board.error} /> : null}
          {plans.isPending || (plan && board.isPending) ? (
            <div className="feed-loading" role="status" aria-label="正在加载学习安排">
              {[0, 1, 2].map((item) => <div className="skeleton" key={item} />)}
            </div>
          ) : null}
          {!plans.isPending && !plans.error && !plan ? (
            <EmptyState title="从一个目标开始" hint="还没有学习计划。"
              action={<Link className="btn" to="/constraint"><Icon name="plus" />制定计划</Link>} />
          ) : null}

          {data ? <>
            <div className="agenda-heading">
              <div>
                <p className="date-label">{view === "today" ? new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(now) : view === "week" ? "本周安排" : "完整学习计划"}</p>
                <h2>{view === "today" ? <>{todayLeft.length}<span>项待办</span></> : view === "week" ? <>{monday.getMonth() + 1}月{monday.getDate()}日<span> — {addDays(monday, 6).getMonth() + 1}月{addDays(monday, 6).getDate()}日</span></> : <>{data.tasks.length}<span>个学习时段</span></>}</h2>
              </div>
              {view === "today" ? <span className="time-total"><Icon name="clock" />{formatMinutes(todayMinutes)}</span> : null}
              {view === "week" ? <div className="week-navigation">
                <button className="btn btn-quiet btn-icon icon-prev" title="上一周" aria-label="上一周" onClick={() => setWeekOffset(weekOffset - 1)}><Icon name="chevron" /></button>
                <button className="btn btn-ghost btn-sm" onClick={() => setWeekOffset(0)}>本周</button>
                <button className="btn btn-quiet btn-icon" title="下一周" aria-label="下一周" onClick={() => setWeekOffset(weekOffset + 1)}><Icon name="chevron" /></button>
              </div> : null}
            </div>

            {data.adjust_hint ? <div className="progress-notice"><Icon name="alert" /><p>{data.adjust_hint.message}</p><Link to="/adjust">调整计划<Icon name="arrow" /></Link></div> : null}
            {view === "today" ? <AgendaList tasks={todayTasks} nextId={nextTask?.task_id} onSelect={setSelected} onDone={quickDone} busy={submit.isPending} readonly={data.readonly} /> : null}
            {view === "week" ? <div className="calendar-view">
              <TimetableGrid tasks={data.tasks} monday={monday} onSelect={setSelected} />
              <div className="legend"><span><i />学习</span><span><i />练习</span><span><i />已完成</span></div>
            </div> : null}
            {view === "all" ? <AllList tasks={data.tasks} onSelect={setSelected} onDone={quickDone} busy={submit.isPending} readonly={data.readonly} /> : null}
          </> : null}
        </div>

        <aside className="board-rail" aria-label="学习概览">
          <section className="rail-section course-section">
            <p className="rail-eyebrow">当前课程</p>
            <h2>{plan?.course_name ?? "尚未开始"}</h2>
            <p className="sub">{constraint.data?.deadline ? "截止 " + constraint.data.deadline : "我的学习空间"}</p>
            <div className="course-progress">
              <strong>{progress ? Math.round(rate * 100) : "—"}<span>{progress ? "%" : ""}</span></strong>
              <span>{progress ? progress.done_tasks + " / " + progress.total_tasks + " 项已完成" : "等待学习进度"}</span>
            </div>
            <progress max={100} value={rate * 100} aria-label="课程完成进度" />
            <dl className="course-numbers">
              <div><dt>计划投入</dt><dd>{progress ? formatMinutes(progress.planned_minutes) : "—"}</dd></div>
              <div><dt>实际投入</dt><dd>{progress ? formatMinutes(progress.actual_minutes) : "—"}</dd></div>
            </dl>
            <Link className="rail-link" to="/versions">计划版本 <span>{plan?.current_version ? "v" + plan.current_version : "未确认"}<Icon name="chevron" /></span></Link>
          </section>

          {milestones.length ? <section className="rail-section">
            <div className="rail-heading"><h2>学习路径</h2><span>{milestones.length} 个知识点</span></div>
            <ol className="knowledge-path">
              {milestones.map((name, index) => {
                const done = data?.tasks.filter((task) => task.concept_name === name).every((task) => task.done);
                return <li key={name} data-done={done} data-active={name === nextTask?.concept_name}>
                  <span className="path-node">{done ? <Icon name="check" size={12} /> : String(index + 1).padStart(2, "0")}</span>
                  <span>{name}</span>{name === nextTask?.concept_name ? <small>接下来</small> : null}
                </li>;
              })}
            </ol>
          </section> : null}
          {data?.unscheduled.length ? <section className="rail-section">
            <div className="rail-heading"><h2>未排入任务</h2><span>{data.unscheduled.length} 项</span></div>
            {data.unscheduled.map((row) => <div className="unscheduled-row" key={row.task_id + row.kind}><strong>{row.concept_name}</strong><p className="sub">{formatMinutes(row.minutes)} · {row.reason}</p></div>)}
            <Link className="rail-link" to="/adjust">调整安排<Icon name="arrow" /></Link>
          </section> : null}
          {data?.issues.length ? <section className="rail-section"><h2 className="h2">校验提示</h2><IssueList issues={data.issues} /></section> : null}
          <p className="rail-footer">学径 StudyPath</p>
        </aside>
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

interface AgendaProps {
  tasks: BoardTask[];
  onSelect: (task: BoardTask) => void;
  onDone: (task: BoardTask) => void;
  busy: boolean;
  readonly: boolean;
  nextId?: number;
}

function AgendaList({ tasks, onSelect, onDone, busy, readonly, nextId }: AgendaProps) {
  if (!tasks.length) return <EmptyState title="今天没有安排" hint="今天没有计划中的学习任务。" action={<Link className="btn btn-ghost" to="/adjust">调整计划</Link>} />;
  return <div className="agenda-list">
    {tasks.map((task) => <article key={task.task_id + task.start} className="agenda-item" data-done={task.done}>
      <span className="task-glyph" data-kind={task.kind}><Icon name={task.kind === "study" ? "book" : "practice"} size={22} /></span>
      <div className="agenda-content">
        <div className="task-byline"><strong>{task.kind === "study" ? "知识学习" : "巩固练习"}</strong><span>·</span><time dateTime={task.start}>{formatClock(task.start)}–{formatClock(task.end)}</time>{task.task_id === nextId && !task.done ? <span className="next-label">接下来</span> : null}</div>
        <button className="task-open" onClick={() => onSelect(task)}><h3>{task.concept_name}</h3><Icon name="arrow" size={18} /></button>
        <p className="task-description">{formatMinutes(task.minutes)}{task.slice_total > 1 ? " · 第 " + task.slice_no + " / " + task.slice_total + " 节" : ""}</p>
        <div className="task-actions">
          <button onClick={() => onSelect(task)}><Icon name="draft" />资料与记录</button>
          {!task.done ? <StatusBadge done={false} overdue={task.overdue} conflict={task.issue_codes.length > 0} /> : null}
          <button className="task-complete" disabled={task.done || busy || readonly} onClick={() => onDone(task)}><Icon name="check" />{task.done ? "已完成" : "完成打卡"}</button>
        </div>
      </div>
    </article>)}
  </div>;
}

function AllList(props: AgendaProps) {
  const groups = new Map<string, BoardTask[]>();
  for (const task of props.tasks) {
    const day = task.start.slice(0, 10);
    groups.set(day, [...(groups.get(day) ?? []), task]);
  }
  return <div>{[...groups.entries()].map(([day, tasks]) => <section key={day}>
    <div className="day-divider"><time dateTime={day}>{day}</time><span>{tasks.length} 个时段</span></div>
    <AgendaList {...props} tasks={tasks} />
  </section>)}</div>;
}
