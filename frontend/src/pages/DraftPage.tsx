import { useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { IssueList } from "../components/IssueList";
import { useToast } from "../components/Toast";
import { useConfirmDraft, useGenerateDraft, usePlans } from "../hooks/queries";
import { formatMinutes, formatRange } from "../lib/format";

export function DraftPage() {
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const planId = plan?.plan_id ?? 0;
  const generate = useGenerateDraft(planId);
  const confirm = useConfirmDraft(planId);
  const [confirmKey] = useState(() => crypto.randomUUID());

  const draft = generate.data ?? null;
  const blocked = useMemo(
    () => (draft ? draft.report.issues.some((issue) => issue.level === "ERROR") : false),
    [draft],
  );

  return (
    <Layout>
      <div className="space-y-4">
        <section className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold">草案</h2>
            <p className="text-xs text-slate-500">
              生成 → 校验 → 确认。确认后草案作废，版本不可再改。
            </p>
          </div>
          <div className="flex gap-2">
            <button
              className="btn-ghost"
              disabled={!planId || generate.isPending}
              onClick={() =>
                generate.mutate(undefined, {
                  onSuccess: () => toast.push("草案已生成", "success"),
                  onError: (error) =>
                    toast.push(error instanceof Error ? error.message : "生成失败", "error"),
                })
              }
            >
              生成草案
            </button>
            <button
              className="btn-primary"
              disabled={!draft || blocked || confirm.isPending}
              onClick={() =>
                draft &&
                confirm.mutate(
                  { revision: draft.revision, confirmKey },
                  {
                    onSuccess: (data) =>
                      toast.push(
                        data.replayed ? "重复提交，返回原版本 v" + data.version_no : "已确认 v" + data.version_no,
                        "success",
                      ),
                    onError: (error) =>
                      toast.push(error instanceof Error ? error.message : "确认失败", "error"),
                  },
                )
              }
            >
              确认生效
            </button>
          </div>
        </section>

        {!planId ? <p className="text-sm text-slate-500">请先在「约束」页创建计划。</p> : null}

        <ErrorBox error={generate.error ?? confirm.error} />

        {draft ? (
          <>
            <section className="card grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <Metric label="任务总时长 T" value={formatMinutes(draft.metrics.total_minutes)} />
              <Metric label="可排容量 C′" value={formatMinutes(draft.metrics.usable_minutes)} />
              <Metric label="缺口 D" value={formatMinutes(draft.metrics.deficit_minutes)} />
              <Metric label="利用率 U" value={(draft.metrics.utilization * 100).toFixed(1) + "%"} />
            </section>

            <section className="card">
              <h3 className="text-sm font-semibold text-slate-700">校验结果</h3>
              <div className="mt-2">
                <IssueList issues={draft.report.issues} />
              </div>
            </section>

            <section className="card">
              <h3 className="text-sm font-semibold text-slate-700">任务（{draft.tasks.length}）</h3>
              <table className="mt-2 w-full text-sm">
                <thead className="text-left text-xs text-slate-500">
                  <tr>
                    <th className="py-1">知识点</th>
                    <th>类型</th>
                    <th>时长</th>
                    <th>片数</th>
                  </tr>
                </thead>
                <tbody>
                  {draft.tasks.map((task) => {
                    const slices = draft.slices.filter(
                      (slice) => slice.concept_id === task.concept_id && slice.kind === task.kind,
                    );
                    return (
                      <tr key={task.concept_id + task.kind} className="border-t border-slate-100">
                        <td className="py-1">知识点 {task.concept_id}</td>
                        <td>{task.kind === "study" ? "学习" : "练习"}</td>
                        <td>{formatMinutes(task.minutes)}</td>
                        <td>
                          {slices.length}
                          {slices.length ? (
                            <span className="ml-1 text-xs text-slate-400">
                              {formatRange(slices[0].start, slices[0].end)}
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>

            {draft.unscheduled.length ? (
              <section className="card">
                <h3 className="text-sm font-semibold text-rose-700">未排入</h3>
                <ul className="mt-1 text-sm">
                  {draft.unscheduled.map((row) => (
                    <li key={row.concept_id + row.kind}>
                      知识点 {row.concept_id}（{row.kind}）· {row.reason}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </Layout>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}
