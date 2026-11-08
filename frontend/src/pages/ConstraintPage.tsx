import { useEffect, useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import {
  useConcepts, useConstraint, useCreatePlan, useExtract, usePlans, usePreviewCapacity,
  useSaveConstraint,
} from "../hooks/queries";
import { WEEKDAY_KEYS, WEEKDAY_LABELS, addDays, formatMinutes, parseClock, todayLocalISO } from "../lib/format";

type Week = Record<string, [string, string][]>;

const EMPTY_WEEK: Week = { mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: [] };

export function ConstraintPage() {
  const toast = useToast();
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const concepts = useConcepts(1);
  const saved = useConstraint(plan?.plan_id ?? null);
  const createPlan = useCreatePlan();
  const extract = useExtract();
  const preview = usePreviewCapacity(plan?.plan_id ?? 0);
  const save = useSaveConstraint(plan?.plan_id ?? 0);

  const [utterance, setUtterance] = useState("");
  const [target, setTarget] = useState<number | "">("");
  const [deadline, setDeadline] = useState(addDays(todayLocalISO(), 14));
  const [dailyLimit, setDailyLimit] = useState(480);
  const [week, setWeek] = useState<Week>(EMPTY_WEEK);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [mastered, setMastered] = useState<number[]>([]);
  const [questions, setQuestions] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<{ concept_id: number; name: string }[]>([]);
  const [mode, setMode] = useState<string>("");

  useEffect(() => {
    const data = saved.data;
    if (!data) return;
    setTarget(data.target_concept_id);
    setDeadline(data.deadline);
    const next: Week = { ...EMPTY_WEEK };
    for (const key of WEEKDAY_KEYS) {
      const segs = data.availability?.[key];
      if (segs?.length) next[key] = segs.map(([s, e]) => [s, e] as [string, string]);
    }
    setWeek(next);
    setExcluded(data.excluded_dates ?? []);
    setMastered(data.mastered_concept_ids ?? []);
  }, [saved.data]);

  const payload = useMemo(
    () => ({
      target_concept_id: target === "" ? 0 : Number(target),
      deadline,
      availability: Object.fromEntries(
        WEEKDAY_KEYS.filter((key) => week[key].length > 0).map((key) => [key, week[key]]),
      ),
      excluded_dates: excluded,
      mastered_concept_ids: mastered,
      daily_limit: dailyLimit,
    }),
    [target, deadline, week, excluded, mastered, dailyLimit],
  );

  function applyExtraction() {
    if (!plan) {
      toast.push("请先创建学习计划", "error");
      return;
    }
    extract.mutate(
      { utterance, filled: {} },
      {
        onSuccess: (data) => {
          setMode(data.mode);
          setQuestions(data.questions);
          setCandidates(data.candidates);
          if (typeof data.fields.target_concept_id === "number") {
            setTarget(data.fields.target_concept_id);
          }
          if (typeof data.fields.deadline === "string") setDeadline(data.fields.deadline);
          if (typeof data.fields.daily_limit === "number") setDailyLimit(data.fields.daily_limit);
          const warnings = data.warnings ?? [];
          if (warnings.length) toast.push(warnings.join("；"), "info");
          if (data.degraded_reason) toast.push("已降级：" + data.degraded_reason, "info");
          if (data.questions.length) toast.push("还需要补充 " + data.questions.length + " 项", "info");
        },
        onError: (error) => toast.push(error instanceof Error ? error.message : "抽取失败", "error"),
      },
    );
  }

  function doPreview() {
    if (!plan) {
      toast.push("请先创建学习计划", "error");
      return;
    }
    preview.mutate(payload, {
      onError: (error) => toast.push(error instanceof Error ? error.message : "预览失败", "error"),
    });
  }

  function doSave() {
    if (!plan) {
      toast.push("请先创建学习计划", "error");
      return;
    }
    save.mutate(payload, {
      onSuccess: () => toast.push("约束已保存", "success"),
      onError: (error) => toast.push(error instanceof Error ? error.message : "保存失败", "error"),
    });
  }

  function updateSlot(key: string, index: number, position: 0 | 1, value: string) {
    setWeek((prev) => {
      const next: Week = { ...prev, [key]: prev[key].map((seg) => [...seg] as [string, string]) };
      next[key][index][position] = value;
      return next;
    });
  }

  function addSlot(key: string) {
    setWeek((prev) => ({ ...prev, [key]: [...prev[key], ["19:00", "21:00"]] }));
  }

  function removeSlot(key: string, index: number) {
    setWeek((prev) => ({ ...prev, [key]: prev[key].filter((_, i) => i !== index) }));
  }

  const course = concepts.data?.items ?? [];
  const summary = preview.data ?? save.data ?? null;

  return (
    <Layout>
      <div className="space-y-4">
        <section className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">学习约束</h2>
            <p className="text-xs text-slate-500">
              先写一句话，系统抽取字段；不够的会追问，最多问两项。
            </p>
          </div>
          {plan ? null : (
            <button
              className="btn-primary"
              disabled={createPlan.isPending}
              onClick={() =>
                createPlan.mutate(1, {
                  onSuccess: () => toast.push("已创建学习计划", "success"),
                  onError: (error) =>
                    toast.push(error instanceof Error ? error.message : "创建失败", "error"),
                })
              }
            >
              创建学习计划
            </button>
          )}
        </section>

        <section className="card space-y-2">
          <label className="label" htmlFor="utterance">用一句话说清楚</label>
          <div className="flex gap-2">
            <input
              id="utterance"
              className="input"
              placeholder="例如：我想学指针，10 天后，每天两小时，工作日晚上有空"
              value={utterance}
              onChange={(event) => setUtterance(event.target.value)}
            />
            <button className="btn-primary whitespace-nowrap" disabled={!utterance || extract.isPending}
                    onClick={applyExtraction}>
              抽取
            </button>
          </div>
          <p className="text-xs text-slate-500">
            当前模式：{mode || "local"}（模型不可用时自动降级，已填内容不丢）
          </p>
          {questions.length ? (
            <ul className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {questions.map((question) => (
                <li key={question}>· {question}</li>
              ))}
            </ul>
          ) : null}
          {candidates.length ? (
            <div className="rounded border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">没匹配到唯一知识点，请从候选里选：</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {candidates.map((item) => (
                  <button
                    key={item.concept_id}
                    className="btn-ghost"
                    onClick={() => setTarget(item.concept_id)}
                  >
                    {item.name}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="card grid gap-3 sm:grid-cols-3">
          <div>
            <label className="label" htmlFor="target">主目标</label>
            <select
              id="target"
              className="input"
              value={target}
              onChange={(event) => setTarget(event.target.value === "" ? "" : Number(event.target.value))}
            >
              <option value="">请选择</option>
              {course.filter((item) => item.status === "enabled").map((item) => (
                <option key={item.concept_id} value={item.concept_id}>
                  {item.name}（{item.reference_minutes} 分钟）
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="deadline">截止日期</label>
            <input
              id="deadline"
              type="date"
              className="input"
              value={deadline}
              onChange={(event) => setDeadline(event.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="dailyLimit">每日上限（分钟）</label>
            <input
              id="dailyLimit"
              type="number"
              className="input"
              value={dailyLimit}
              min={30}
              max={480}
              onChange={(event) => setDailyLimit(Number(event.target.value))}
            />
          </div>
        </section>

        <section className="card space-y-2">
          <h3 className="text-sm font-semibold text-slate-700">每周可用时间</h3>
          <div className="space-y-2">
            {WEEKDAY_KEYS.map((key, index) => (
              <div key={key} className="flex flex-wrap items-center gap-2">
                <span className="w-12 text-sm text-slate-600">{WEEKDAY_LABELS[index]}</span>
                {week[key].map((seg, segIndex) => (
                  <span key={segIndex} className="flex items-center gap-1">
                    <input
                      className="input w-20"
                      value={seg[0]}
                      onChange={(event) => updateSlot(key, segIndex, 0, parseClock(event.target.value))}
                      aria-label={WEEKDAY_LABELS[index] + " 开始"}
                    />
                    <span>-</span>
                    <input
                      className="input w-20"
                      value={seg[1]}
                      onChange={(event) => updateSlot(key, segIndex, 1, parseClock(event.target.value))}
                      aria-label={WEEKDAY_LABELS[index] + " 结束"}
                    />
                    <button className="btn-ghost" onClick={() => removeSlot(key, segIndex)}>
                      删除
                    </button>
                  </span>
                ))}
                {week[key].length < 3 ? (
                  <button className="btn-ghost" onClick={() => addSlot(key)}>
                    + 时段
                  </button>
                ) : null}
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-500">每天最多 3 段、合计不超过 8 小时。</p>
        </section>

        <section className="card grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="excluded">排除日期（逗号分隔）</label>
            <input
              id="excluded"
              className="input"
              placeholder="2026-11-15,2026-11-16"
              value={excluded.join(",")}
              onChange={(event) =>
                setExcluded(
                  event.target.value
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                )
              }
            />
          </div>
          <div>
            <label className="label">已掌握（不计入任务）</label>
            <div className="flex flex-wrap gap-2">
              {course.map((item) => (
                <label key={item.concept_id} className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={mastered.includes(item.concept_id)}
                    onChange={(event) =>
                      setMastered((prev) =>
                        event.target.checked
                          ? [...prev, item.concept_id]
                          : prev.filter((id) => id !== item.concept_id),
                      )
                    }
                  />
                  {item.name}
                </label>
              ))}
            </div>
          </div>
        </section>

        <div className="flex items-center gap-2">
          <button className="btn-ghost" onClick={doPreview} disabled={preview.isPending}>
            预览容量
          </button>
          <button className="btn-primary" onClick={doSave} disabled={save.isPending}>
            保存约束
          </button>
        </div>

        <ErrorBox error={preview.error ?? save.error} />

        {summary ? (
          <section className="card">
            <h3 className="text-sm font-semibold text-slate-700">容量</h3>
            <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <Item label="原始容量 C" value={formatMinutes(summary.C)} />
              <Item label="缓冲 B（10%）" value={formatMinutes(summary.B)} />
              <Item label="可排 C′" value={formatMinutes(summary.C_prime)} />
              <Item label="目标路径" value={formatMinutes(summary.path_minutes)} />
            </dl>
            <p className="mt-2 text-xs text-slate-500">共 {summary.slots} 个可用时段。</p>
            {summary.reject_reason ? (
              <p className="mt-1 text-sm text-rose-600">
                不可排原因：{summary.reject_reason}
              </p>
            ) : null}
          </section>
        ) : null}
      </div>
    </Layout>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
