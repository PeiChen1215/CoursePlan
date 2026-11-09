import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { Card, CardHead, EmptyState } from "../components/ui";
import { useEvents, usePlans } from "../hooks/queries";
import { formatMinutes } from "../lib/format";

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

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">学习记录</h1>
          <p className="sub">
            打卡、更正、备注都记在这里。事件只追加，不删除；更正会指向被更正的那一条。
          </p>
        </div>
        <span className="chip">{items.length} 条记录</span>
      </header>

      <div className="stack">
        {events.error ? <ErrorBox error={events.error} /> : null}

        {items.length === 0 ? (
          <EmptyState
            title="还没有记录"
            hint="在看板上点一个任务块就能打卡，或者直接勾掉「今天」里的待办。"
          />
        ) : (
          <Card>
            <CardHead title="按时间倒序" hint="最近的记录在最上面" />
            <div className="card-body" style={{ paddingTop: 4 }}>
              {items.map((row) => (
                <div key={row.event_id} className="row-item" style={{ alignItems: "flex-start" }}>
                  <span className="mono-sm" style={{ width: 108, flex: "none" }}>
                    {row.occurred_at.slice(5, 16).replace("T", " ")}
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
