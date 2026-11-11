import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { Card, CardHead, EmptyState, Segmented } from "../components/ui";
import { useEvents, usePlans } from "../hooks/queries";
import { formatDateTime, formatMinutes } from "../lib/format";

const TONE: Record<string, "done" | "brand" | "warn"> = {
  done: "done",
  correction: "warn",
  note: "brand",
};

export function TimelinePage() {
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const events = useEvents(plan?.plan_id ?? null);
  const items = events.data?.items ?? [];
  const [filter, setFilter] = useState("all");
  const visible = filter === "all" ? items : items.filter((item) => item.event_type === filter);

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">学习记录</h1>
          <p className="sub">
            {plan?.course_name ?? "我的课程"} · 每一步努力都有迹可循
          </p>
        </div>
        <span className="chip">{items.length} 条记录</span>
      </header>

      <div className="stack">
        {events.error ? <ErrorBox error={events.error} /> : null}
        <Segmented value={filter} onChange={setFilter} options={[
          { value: "all", label: "全部" }, { value: "done", label: "打卡" },
          { value: "correction", label: "更正" }, { value: "note", label: "备注" },
        ]} />

        {items.length === 0 ? (
          <EmptyState
            title="还没有记录"
            hint="在看板上点一个任务块就能打卡，或者直接勾掉「今天」里的待办。"
          />
        ) : (
          <Card>
            <CardHead title="学习足迹" action={<span className="mono-sm">{visible.length} 条</span>} />
            <div className="card-body" style={{ paddingTop: 4 }}>
              {!visible.length ? <EmptyState title="暂无此类记录" /> : null}
              {visible.map((row) => (
                <div key={row.event_id} className="row-item timeline-event" data-type={row.event_type} style={{ alignItems: "flex-start" }}>
                  <span className="mono-sm" style={{ width: 108, flex: "none" }}>
                    {formatDateTime(row.occurred_at)}
                  </span>
                  <span className="chip" data-tone={TONE[row.event_type] ?? "brand"}>{row.label}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p className="row-title">
                      {row.concept_name}
                      {row.task_type ? (
                        <span className="faint"> · {row.task_type === "study" ? "学习" : "练习"}</span>
                      ) : null}
                      {row.actual_minutes != null ? (
                        <span className="num faint"> · {formatMinutes(row.actual_minutes)}</span>
                      ) : null}
                    </p>
                    {row.note ? <p className="row-sub">{row.note}</p> : null}
                    {row.corrects_event_id ? (
                      <p className="row-sub">更正了 #{row.corrects_event_id}</p>
                    ) : null}
                  </div>
                  <span className="row-sub num">
                    v{row.version_no ?? "—"}
                    {row.is_current_version ? "（当前）" : ""}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </Layout>
  );
}
import { useState } from "react";
