import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { IssueList } from "../components/IssueList";
import { useToast } from "../components/Toast";
import { useConfirmDraft, useGenerateDraft, usePlans } from "../hooks/queries";
import { formatMinutes } from "../lib/format";

export function DraftPage() {
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const planId = plan?.plan_id ?? 0;
  const generate = useGenerateDraft(planId);
  const confirm = useConfirmDraft(planId);
  const [confirmKey] = useState(() => crypto.randomUUID());

  const draft = generate.data ?? null;
  const blocked = draft ? draft.report.issues.some((issue) => issue.level === "ERROR") : true;

  return (
    <Layout>
      <div className="space-y-6">
        <section className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="display text-xl">草案</h2>
            <p className="faint mt-1 text-xs">
              按约束生成一份草案，校验通过才能确认。确认后草案作废，版本不可再改。
            </p>
          </div>
          <div className="flex gap-3">
            <button className="btn btn-quiet" disabled={!planId || generate.isPending}
                    onClick={() => generate.mutate(undefined, {
                      onSuccess: () => toast.push("草案已生成", "success"),
                      onError: (error) =>
                        toast.push(error instanceof Error ? error.message : "生成失败", "error"),
                    })}>
              生成草案
            </button>
            <button className="btn" disabled={!draft || blocked || confirm.isPending}
                    onClick={() => draft && confirm.mutate({ revision: draft.revision, confirmKey }, {
                      onSuccess: (data) =>
                        toast.push(data.replayed ? "重复提交，返回原版本" : "已确认生效", "success"),
                      onError: (error) =>
                        toast.push(error instanceof Error ? error.message : "确认失败", "error"),
                    })}>
              确认生效
            </button>
          </div>
        </section>

        {!planId ? <p className="empty">还没有学习计划，先去「填写约束」。</p> : null}
        <ErrorBox error={generate.error ?? confirm.error} />

        {draft ? (
          <>
            <section className="sheet sheet-pad">
              <h3 className="display text-sm">这一版的情况</h3>
              <dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-4">
                <Metric label="任务总时长 T" value={formatMinutes(draft.metrics.total_minutes)} />
                <Metric label="可排容量 C′" value={formatMinutes(draft.metrics.usable_minutes)} />
                <Metric label="缺口 D" value={formatMinutes(draft.metrics.deficit_minutes)} />
                <Metric label="利用率 U" value={(draft.metrics.utilization * 100).toFixed(1) + "%"} />
              </dl>
            </section>

            <section className="sheet sheet-pad">
              <h3 className="display text-sm">校验</h3>
              <div className="mt-2">
                <IssueList issues={draft.report.issues} />
              </div>
              {blocked ? (
                <p className="mt-2 text-sm" style={{ color: "var(--crimson)" }}>
                  存在错误项，不能确认。改约束后重新生成。
                </p>
              ) : null}
            </section>

            <section className="sheet sheet-pad">
              <h3 className="display text-sm">任务清单</h3>
              <table className="ledger mt-2">
                <thead>
                  <tr>
                    <th>知识点</th>
                    <th>类型</th>
                    <th>时长</th>
                    <th>片数</th>
                    <th>首片</th>
                  </tr>
                </thead>
                <tbody>
                  {draft.tasks.map((task) => {
                    const slices = draft.slices.filter(
                      (slice) => slice.concept_id === task.concept_id && slice.kind === task.kind,
                    );
                    return (
                      <tr key={task.concept_id + task.kind}>
                        <td>{task.name || "知识点 " + task.concept_id}</td>
                        <td>{task.kind === "study" ? "学习" : "练习"}</td>
                        <td className="num">{formatMinutes(task.minutes)}</td>
                        <td className="num">{slices.length}</td>
                        <td className="num faint text-xs">
                          {slices[0] ? slices[0].start.slice(5).replace("T", " ") : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
          </>
        ) : (
          <p className="empty">点「生成草案」，系统会闭包、拆分、排序、装箱，然后给出这一版。</p>
        )}
      </div>
    </Layout>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="faint text-xs">{label}</dt>
      <dd className="num text-lg">{value}</dd>
    </div>
  );
}
