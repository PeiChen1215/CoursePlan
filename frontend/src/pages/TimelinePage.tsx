import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useEvents, usePlans } from "../hooks/queries";
import { formatMinutes } from "../lib/format";

export function TimelinePage() {
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const events = useEvents(plan?.plan_id ?? null);
  const items = events.data?.items ?? [];

  return (
    <Layout>
      <div className="space-y-6">
        <section>
          <h2 className="display text-xl">学习记录</h2>
          <p className="faint mt-1 text-xs">
            打卡、更正、备注都记在这里。事件只追加，不删除；更正会指向被更正的那一条。
          </p>
        </section>

        {events.error ? <ErrorBox error={events.error} /> : null}

        {items.length === 0 ? (
          <p className="empty">还没有记录。在看板上点一个任务块就能打卡。</p>
        ) : (
          <section className="sheet sheet-pad">
            <ol>
              {items.map((row) => (
                <li
                  key={row.event_id}
                  className="grid gap-2 border-b py-2 sm:grid-cols-[7rem_1fr_6rem]"
                  style={{ borderColor: "var(--rule)" }}
                >
                  <span className="num faint text-xs">{row.occurred_at.slice(5, 16).replace("T", " ")}</span>
                  <span className="text-sm">
                    {row.label}
                    <span className="faint"> · {row.concept_name}</span>
                    {row.task_type ? (
                      <span className="faint">（{row.task_type === "study" ? "学习" : "练习"}）</span>
                    ) : null}
                    {row.actual_minutes != null ? (
                      <span className="num"> {formatMinutes(row.actual_minutes)}</span>
                    ) : null}
                    {row.note ? <span className="muted"> — {row.note}</span> : null}
                    {row.corrects_event_id ? (
                      <span className="faint text-xs"> 更正了 #{row.corrects_event_id}</span>
                    ) : null}
                  </span>
                  <span className="faint num text-xs">
                    v{row.version_no ?? "—"}
                    {row.is_current_version ? "（当前）" : ""}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </Layout>
  );
}
