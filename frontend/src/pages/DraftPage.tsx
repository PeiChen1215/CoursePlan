import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { IssueList } from "../components/IssueList";
import { useToast } from "../components/Toast";
import {
  useConfirmDraft, useGenerateDraft, useOverrideTasks, usePlans,
} from "../hooks/queries";
import { formatMinutes } from "../lib/format";

export function DraftPage() {
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const planId = plan?.plan_id ?? 0;
  const generate = useGenerateDraft(planId);
  const confirm = useConfirmDraft(planId);
  const override = useOverrideTasks(planId);
  const [confirmKey] = useState(() => crypto.randomUUID());
  const [edited, setEdited] = useState<Record<string, string>>({});

  const draft = generate.data ?? null;
  const keyOf = (conceptId: number, kind: string) => conceptId + "-" + kind;
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
        <ErrorBox error={generate.error ?? confirm.error ?? override.error} />

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
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="display text-sm">任务清单</h3>
                <span className="faint text-xs">
                  觉得估得不准可以直接改分钟数，然后重排（覆盖值不会改课程原始参考时长）
                </span>
              </div>
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
                        <td>
                          <input
                            aria-label={"时长 " + task.concept_id + task.kind}
                            className="input num"
                            style={{ width: "4.5rem" }}
                            value={edited[keyOf(task.concept_id, task.kind)] ?? String(task.minutes)}
                            onChange={(event) =>
                              setEdited((prev) => ({
                                ...prev,
                                [keyOf(task.concept_id, task.kind)]: event.target.value,
                              }))
                            }
                            inputMode="numeric"
                          />
                          <span className="faint text-xs"> 分</span>
                        </td>
                        <td className="num">{slices.length}</td>
                        <td className="num faint text-xs">
                          {slices[0] ? slices[0].start.slice(5).replace("T", " ") : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="mt-3">
                <button
                  className="btn btn-quiet"
                  disabled={override.isPending || Object.keys(edited).length === 0}
                  onClick={() => {
                    const items = draft.tasks
                      .map((task) => {
                        const raw = edited[keyOf(task.concept_id, task.kind)];
                        if (raw === undefined) return null;
                        const minutes = Number(raw);
                        if (!Number.isFinite(minutes) || minutes <= 0) return null;
                        if (minutes === task.minutes) return null;
                        return { concept_id: task.concept_id, kind: task.kind, minutes };
                      })
                      .filter(Boolean) as { concept_id: number; kind: string; minutes: number }[];
                    if (!items.length) {
                      toast.push("没有改动", "info");
                      return;
                    }
                    override.mutate(
                      { revision: draft.revision, items },
                      {
                        onSuccess: () => {
                          toast.push("已按新时长重排，请重新生成查看新版草案", "success");
                          setEdited({});
                        },
                        onError: (error) =>
                          toast.push(error instanceof Error ? error.message : "重排失败", "error"),
                      },
                    );
                  }}
                >
                  按新时长重排
                </button>
              </div>
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
