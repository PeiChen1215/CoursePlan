import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { IssueList } from "../components/IssueList";
import { useToast } from "../components/Toast";
import { Card, CardHead, Field, Icon, Stat } from "../components/ui";
import {
  useConfirmDraft, useConstraint, useGenerateDraft, usePlans, useSaveConstraint, useVersions,
} from "../hooks/queries";
import { formatMinutes } from "../lib/format";

const REASONS = [
  { value: "delay", label: "进度落后了", hint: "任务没按计划完成，需要往后顺延" },
  { value: "goal_change", label: "目标变了", hint: "想学的知识点有增减" },
  { value: "availability_change", label: "可用时间变了", hint: "每周能学的时间段变了" },
  { value: "duration_change", label: "时长估错了", hint: "某些知识点比预期更费时间" },
];

const LABEL: Record<string, string> = {
  added: "新增", removed: "移除", moved: "移动", resized: "时长变化",
};

export function AdjustPage() {
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const planId = plan?.plan_id ?? 0;
  const constraint = useConstraint(planId || null);
  const versions = useVersions(planId || null);
  const saveConstraint = useSaveConstraint(planId);
  const generate = useGenerateDraft(planId);
  const confirm = useConfirmDraft(planId);

  const [reason, setReason] = useState("delay");
  const [note, setNote] = useState("");
  const [newDeadline, setNewDeadline] = useState("");
  const [confirmKey] = useState(() => crypto.randomUUID());

  const current = constraint.data;
  const effectiveDeadline = newDeadline || current?.deadline || "";
  const deadlineChanged = Boolean(current && newDeadline && newDeadline !== current.deadline);

  const draft = generate.data ?? null;
  const blocked = draft ? draft.report.issues.some((i) => i.level === "ERROR") : true;
  const diff = draft?.diff;
  const diffCount = diff
    ? diff.added.length + diff.removed.length + diff.moved.length + diff.resized.length
    : 0;

  async function replan() {
    if (deadlineChanged && current) {
      await saveConstraint.mutateAsync({
        target_concept_id: current.target_concept_id,
        extra_concept_ids: current.extra_concept_ids,
        deadline: newDeadline,
        availability: current.availability,
        excluded_dates: current.excluded_dates,
        mastered_concept_ids: current.mastered_concept_ids,
      });
    }
    generate.mutate(undefined, {
      onSuccess: () =>
        toast.push(deadlineChanged ? "已按新截止日期重排" : "已按当前约束重排", "success"),
      onError: (error) =>
        toast.push(error instanceof Error ? error.message : "生成失败", "error"),
    });
  }

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">调整计划</h1>
          <p className="sub">{plan?.course_name ?? "我的课程"} · 让计划跟上你的节奏</p>
        </div>
        {plan?.current_version ? (
          <span className="chip" data-tone="brand">当前 v{plan.current_version}</span>
        ) : null}
      </header>

      <div className="grid-2">
        <div className="stack">
          <Card>
            <CardHead title="为什么调整" hint="原因会写进版本记录" />
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {REASONS.map((item) => (
                  <label
                    key={item.value}
                    className="check"
                    data-on={reason === item.value}
                    style={{ alignItems: "flex-start", padding: "10px 12px" }}
                  >
                    <input
                      type="radio"
                      name="reason"
                      value={item.value}
                      checked={reason === item.value}
                      onChange={() => setReason(item.value)}
                      style={{ marginTop: 3 }}
                    />
                    <span>
                      <span style={{ display: "block", fontWeight: 550 }}>{item.label}</span>
                      <span className="field-hint">{item.hint}</span>
                    </span>
                  </label>
                ))}
              </div>

              <div className="stack" style={{ gap: 12, marginTop: 14 }}>
                <Field label="新的截止日期" hint={deadlineChanged ? "改完会先更新约束，再重排" : "不改就按原截止日期重排"}>
                  <input
                    className="input num"
                    style={{ width: 180 }}
                    type="date"
                    value={effectiveDeadline}
                    onChange={(event) => setNewDeadline(event.target.value)}
                  />
                </Field>
                <Field label="补充说明">
                  <input
                    className="input"
                    placeholder="例如：工作量大，截止日期延后到 12-20"
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                </Field>
              </div>

              <div style={{ marginTop: 14 }}>
                <button className="btn" disabled={!planId || generate.isPending || saveConstraint.isPending}
                        onClick={replan}>
                  <Icon name="spark" size={15} />
                  重排并预览
                </button>
              </div>
            </div>
          </Card>

          {!planId ? <p className="empty">还没有学习计划，先去「填写约束」。</p> : null}

          {planId && !draft ? (
            <Card className="card-pad" quiet>
              <p className="h3">接下来会发生什么</p>
              <ol className="sub" style={{ margin: "8px 0 0", paddingLeft: 18, lineHeight: 1.9 }}>
                <li>选一个原因，必要时改截止日期</li>
                <li>重排后先看差异与新容量，不会立即生效</li>
                <li>确认之后才生成新版本，旧版本整份转只读</li>
              </ol>
            </Card>
          ) : null}
          <ErrorBox error={generate.error ?? confirm.error ?? saveConstraint.error} />

          {draft ? (
            <>
              <Card>
                <CardHead
                  title="与当前版本对比"
                  hint={diffCount === 0 ? "和当前版本没有差别" : "共 " + diffCount + " 处变化"}
                />
                <div className="card-body">
                  <div className="grid-3" style={{ gap: 12 }}>
                    {(["added", "removed", "moved", "resized"] as const).map((key) => (
                      <div key={key} className="card card-quiet card-pad" style={{ padding: "12px 14px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span className="h3">{LABEL[key]}</span>
                          <span className="chip" data-tone={key === "removed" ? "danger" : "brand"}>
                            {diff?.[key].length ?? 0}
                          </span>
                        </div>
                        <p className="row-sub" style={{ marginTop: 6 }}>
                          {diff && diff[key].length ? diff[key].join("、") : "无"}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>

              <div className="stat-strip">
                <Stat label="任务总时长 T" value={formatMinutes(draft.metrics.total_minutes)} />
                <Stat label="可排容量 C′" value={formatMinutes(draft.metrics.usable_minutes)} />
                <Stat label="缺口 D" value={formatMinutes(draft.metrics.deficit_minutes)} />
                <Stat
                  label="利用率 U"
                  value={(draft.metrics.utilization * 100).toFixed(1) + "%"}
                  ratio={draft.metrics.utilization}
                />
              </div>

              <Card>
                <CardHead
                  title="校验"
                  action={
                    <span className="chip" data-tone={blocked ? "danger" : "done"}>
                      {blocked ? "有错误项" : "通过"}
                    </span>
                  }
                />
                <div className="card-body" style={{ paddingTop: 6 }}>
                  <IssueList issues={draft.report.issues} />
                </div>
              </Card>

              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <button
                  className="btn"
                  disabled={blocked || confirm.isPending}
                  onClick={() =>
                    confirm.mutate(
                      { revision: draft.revision, confirmKey, reason, note: note || undefined },
                      {
                        onSuccess: (data) =>
                          toast.push(
                            "已生成 v" + data.version_no + "（" +
                              (REASONS.find((r) => r.value === reason)?.label ?? "调整") + "）",
                            "success",
                          ),
                        onError: (error) =>
                          toast.push(error instanceof Error ? error.message : "确认失败", "error"),
                      },
                    )
                  }
                >
                  确认这次调整
                </button>
                <button className="link-btn" onClick={() => generate.reset()}>取消</button>
                {blocked ? (
                  <span className="field-hint" style={{ color: "var(--danger)" }}>
                    有错误项，先改约束再重排
                  </span>
                ) : null}
              </div>
            </>
          ) : null}
        </div>

        <div className="stack">
          <Card>
            <CardHead title="历史留痕" hint="最近三个版本" />
            <div className="card-body" style={{ paddingTop: 4 }}>
              {(versions.data?.items ?? []).slice(-3).reverse().map((row) => (
                <div key={row.version_no} className="row-item" style={{ alignItems: "flex-start" }}>
                  <span className="chip" data-tone="brand">v{row.version_no}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p className="row-title">{row.change_reason}</p>
                    <p className="row-sub">{row.change_note}</p>
                  </div>
                </div>
              ))}
              {versions.data?.items.length ? null : (
                <p className="sub">还没有历史版本</p>
              )}
            </div>
          </Card>

          <Card className="card-pad" quiet>
            <p className="h3">调整会保留什么</p>
            <p className="sub" style={{ marginTop: 6 }}>
              已完成的打卡记录不会改动；旧版本整份转只读，随时可以对比。
              只有确认之后，新版本才会生效。
            </p>
          </Card>
        </div>
      </div>
    </Layout>
  );
}
