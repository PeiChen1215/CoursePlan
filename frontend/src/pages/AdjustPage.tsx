import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { IssueList } from "../components/IssueList";
import { useToast } from "../components/Toast";
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
  const versions = useVersions(planId || null);
  const constraint = useConstraint(planId || null);
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

  const draft = generate.data ?? null;
  const blocked = draft ? draft.report.issues.some((i) => i.level === "ERROR") : true;
  const diff = draft?.diff;
  const diffCount = diff
    ? diff.added.length + diff.removed.length + diff.moved.length + diff.resized.length
    : 0;

  return (
    <Layout>
      <div className="space-y-6">
        <section>
          <h2 className="display text-xl">调整计划</h2>
          <p className="faint mt-1 text-xs">
            先说清为什么调整，再重新生成。确认后会产生新版本，旧版本转只读。
          </p>
        </section>

        <section className="sheet sheet-pad">
          <h3 className="display text-sm">为什么调整</h3>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {REASONS.map((item) => (
              <label
                key={item.value}
                className="flex cursor-pointer items-start gap-2 rounded-sm border p-2 text-sm"
                style={{
                  borderColor: reason === item.value ? "var(--ink)" : "var(--rule)",
                  background: reason === item.value ? "rgba(228,240,140,.18)" : "transparent",
                }}
              >
                <input
                  type="radio"
                  name="reason"
                  value={item.value}
                  checked={reason === item.value}
                  onChange={() => setReason(item.value)}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium">{item.label}</span>
                  <span className="faint block text-xs">{item.hint}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="field-row mt-3">
            <label htmlFor="adj-deadline">新的截止日期</label>
            <div className="flex items-baseline gap-3">
              <input
                id="adj-deadline"
                type="date"
                className="input num"
                style={{ width: "12rem" }}
                value={effectiveDeadline}
                onChange={(event) => setNewDeadline(event.target.value)}
              />
              <span className="faint text-xs">
                {deadlineChanged ? "改完会先更新约束，再重排" : "不改就按原截止日期重排"}
              </span>
            </div>
          </div>
          <div className="field-row mt-3">
            <label htmlFor="adj-note">补充说明</label>
            <input
              id="adj-note"
              className="input"
              placeholder="例如：工作量大，截止日期延后到 12-20"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </div>
          <div className="mt-3 flex items-center gap-3">
            <button className="btn" disabled={!planId || generate.isPending || saveConstraint.isPending}
                    onClick={replan}>
              重排并预览
            </button>
            <span className="faint text-xs">
              {plan?.current_version ? "当前生效：v" + plan.current_version : "还没有生效版本"}
            </span>
          </div>
        </section>

        {!planId ? <p className="empty">还没有学习计划，先去「填写约束」。</p> : null}
        <ErrorBox error={generate.error ?? confirm.error ?? saveConstraint.error} />

        {draft ? (
          <>
            <section className="sheet sheet-pad">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h3 className="display text-sm">与当前版本对比</h3>
                <span className="faint text-xs">
                  {diffCount === 0
                    ? "和当前版本没有差别"
                    : "共 " + diffCount + " 处变化"}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
                {(["added", "removed", "moved", "resized"] as const).map((key) => (
                  <div key={key}>
                    <p className="text-xs" style={{ color: key === "removed" ? "var(--crimson)" : "var(--ink-2)" }}>
                      {LABEL[key]} <span className="num">{diff?.[key].length ?? 0}</span>
                    </p>
                    <p className="faint mt-1 text-xs">
                      {diff && diff[key].length ? diff[key].join("、") : "无"}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="sheet sheet-pad">
              <h3 className="display text-sm">新的容量情况</h3>
              <dl className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 text-sm sm:grid-cols-4">
                <div>
                  <dt className="faint text-xs">任务总时长 T</dt>
                  <dd className="num">{formatMinutes(draft.metrics.total_minutes)}</dd>
                </div>
                <div>
                  <dt className="faint text-xs">可排容量 C′</dt>
                  <dd className="num">{formatMinutes(draft.metrics.usable_minutes)}</dd>
                </div>
                <div>
                  <dt className="faint text-xs">缺口 D</dt>
                  <dd className="num">{formatMinutes(draft.metrics.deficit_minutes)}</dd>
                </div>
                <div>
                  <dt className="faint text-xs">利用率 U</dt>
                  <dd className="num">{(draft.metrics.utilization * 100).toFixed(1)}%</dd>
                </div>
              </dl>
            </section>

            <section className="sheet sheet-pad">
              <h3 className="display text-sm">校验</h3>
              <div className="mt-2">
                <IssueList issues={draft.report.issues} />
              </div>
            </section>

            <div className="flex items-center gap-3">
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
              <button className="btn-link text-xs" onClick={() => generate.reset()}>
                取消
              </button>
              {blocked ? (
                <span className="text-xs" style={{ color: "var(--crimson)" }}>
                  有错误项，先改约束再重排
                </span>
              ) : null}
            </div>

            <section className="sheet sheet-pad">
              <h3 className="display text-sm">历史留痕</h3>
              <ul className="mt-2 text-xs muted">
                {(versions.data?.items ?? []).slice(-3).reverse().map((row) => (
                  <li key={row.version_no} className="border-b py-1" style={{ borderColor: "var(--rule)" }}>
                    v{row.version_no} · {row.change_reason} · {row.change_note}
                  </li>
                ))}
                {versions.data?.items.length ? null : <li className="faint">还没有历史版本</li>}
              </ul>
            </section>
          </>
        ) : null}
      </div>
    </Layout>
  );
}
