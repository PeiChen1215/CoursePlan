import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { IssueList } from "../components/IssueList";
import { useToast } from "../components/Toast";
import { Card, CardHead, EmptyState, Icon, Stat } from "../components/ui";
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
      <header className="page-head">
        <div>
          <h1 className="h1">草案</h1>
          <p className="sub">按约束生成一份草案，校验通过才能确认。确认后草案作废，版本不可再改。</p>
        </div>
        <div className="page-head-actions">
          <button className="btn btn-ghost" disabled={!planId || generate.isPending}
                  onClick={() => generate.mutate(undefined, {
                    onSuccess: () => toast.push("草案已生成", "success"),
                    onError: (error) =>
                      toast.push(error instanceof Error ? error.message : "生成失败", "error"),
                  })}>
            <Icon name="spark" size={15} />
            生成草案
          </button>
          <button className="btn" disabled={!draft || blocked || confirm.isPending}
                  onClick={() => draft && confirm.mutate({ revision: draft.revision, confirmKey }, {
                    onSuccess: (data) =>
                      toast.push(data.replayed ? "重复提交，返回原版本" : "已确认生效 v" + data.version_no, "success"),
                    onError: (error) =>
                      toast.push(error instanceof Error ? error.message : "确认失败", "error"),
                  })}>
            确认生效
          </button>
        </div>
      </header>

      <div className="stack">
        {!planId ? <p className="empty">还没有学习计划，先去「填写约束」。</p> : null}
        <ErrorBox error={generate.error ?? confirm.error ?? override.error} />

        {draft ? (
          <>
            <div className="stat-strip">
              <Stat label="任务总时长 T" value={formatMinutes(draft.metrics.total_minutes)} />
              <Stat label="可排容量 C′" value={formatMinutes(draft.metrics.usable_minutes)} />
              <Stat
                label="缺口 D"
                value={formatMinutes(draft.metrics.deficit_minutes)}
                unit={draft.metrics.deficit_minutes > 0 ? " 排不下" : ""}
              />
              <Stat
                label="利用率 U"
                value={(draft.metrics.utilization * 100).toFixed(1) + "%"}
                ratio={draft.metrics.utilization}
              />
            </div>

            <Card>
              <CardHead
                title="校验"
                hint={blocked ? "有错误项，先改约束再确认" : "全部通过"}
                action={
                  <span className="chip" data-tone={blocked ? "danger" : "done"}>
                    {blocked ? "未通过" : "通过"}
                  </span>
                }
              />
              <div className="card-body" style={{ paddingTop: 6 }}>
                <IssueList issues={draft.report.issues} />
              </div>
            </Card>

            <Card>
              <CardHead
                title="任务清单"
                hint="觉得估得不准可以直接改分钟数，然后重排（覆盖值不改课程原始时长）"
                action={
                  <button
                    className="btn btn-ghost btn-sm"
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
                }
              />
              <div className="card-body" style={{ paddingTop: 0, paddingLeft: 8, paddingRight: 8 }}>
                <table className="table">
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
                          <td>
                            <span className="chip" data-tone={task.kind === "study" ? "study" : "practice"}>
                              {task.kind === "study" ? "学习" : "练习"}
                            </span>
                          </td>
                          <td>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <input
                                aria-label={"时长 " + task.concept_id + task.kind}
                                className="input num"
                                style={{ width: 78, height: 30 }}
                                value={edited[keyOf(task.concept_id, task.kind)] ?? String(task.minutes)}
                                onChange={(event) =>
                                  setEdited((prev) => ({
                                    ...prev,
                                    [keyOf(task.concept_id, task.kind)]: event.target.value,
                                  }))
                                }
                                inputMode="numeric"
                              />
                              <span className="row-sub">分</span>
                            </div>
                          </td>
                          <td className="num">{slices.length}</td>
                          <td className="row-sub num">
                            {slices[0] ? slices[0].start.slice(5).replace("T", " ") : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        ) : (
          <EmptyState
            title="还没有草案"
            hint="点「生成草案」，系统会闭包、拆分、排序、装箱，然后给出这一版。"
            action={
              <button className="btn" style={{ marginTop: 6 }} onClick={() => generate.mutate()}>
                生成草案
              </button>
            }
          />
        )}
      </div>
    </Layout>
  );
}
