import { useEffect, useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import {
  useConcepts, useConstraint, useCreatePlan, useExtract, usePlans, usePreviewCapacity,
  useSaveConstraint,
} from "../hooks/queries";
import { formatMinutes } from "../lib/format";
import {
  DAY_KEYS, HOUR_END, HOUR_START, cellId, cellsToRanges, rangesToCells,
} from "../lib/timetable";

const HOURS = Array.from({ length: HOUR_END - HOUR_START }, (_, i) => HOUR_START + i);
const DAY_LABEL = ["一", "二", "三", "四", "五", "六", "日"];

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
  const [deadline, setDeadline] = useState("2026-12-05");
  const [cells, setCells] = useState<Set<string>>(new Set());
  const [excludedText, setExcludedText] = useState("");
  const [mastered, setMastered] = useState<number[]>([]);
  const [questions, setQuestions] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<{ concept_id: number; name: string }[]>([]);
  const [modeText, setModeText] = useState("");
  const [dailyLimit, setDailyLimit] = useState<number | null>(null);
  const [turns, setTurns] = useState<{ mine: string; reply: string }[]>([]);
  const [filled, setFilled] = useState<Record<string, unknown>>({});

  useEffect(() => {
    const data = saved.data;
    if (!data) return;
    setTarget(data.target_concept_id);
    setDeadline(data.deadline);
    setCells(rangesToCells(data.availability ?? {}));
    setExcludedText((data.excluded_dates ?? []).join(", "));
    setMastered(data.mastered_concept_ids ?? []);
  }, [saved.data]);

  const payload = useMemo(() => {
    const excluded = excludedText.split(",").map((s) => s.trim()).filter(Boolean);
    return {
      target_concept_id: target === "" ? 0 : Number(target),
      deadline,
      availability: cellsToRanges(cells),
      excluded_dates: excluded,
      mastered_concept_ids: mastered,
    };
  }, [target, deadline, cells, excludedText, mastered]);

  function toggle(day: string, hour: number) {
    setCells((prev) => {
      const next = new Set(prev);
      const id = cellId(day as (typeof DAY_KEYS)[number], hour);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function runExtract() {
    if (!plan) {
      toast.push("先创建一份学习计划", "error");
      return;
    }
    const said = utterance;
    extract.mutate({ utterance, filled }, {
      onSuccess: (data) => {
        setModeText(data.mode);
        setQuestions(data.questions);
        setCandidates(data.candidates);
        setFilled((prev) => ({ ...prev, ...data.fields }));
        setTurns((prev) => [...prev, {
          mine: said,
          reply: data.questions.length
            ? "还差：" + data.questions.join("；")
            : "字段齐了，可以保存。",
        }]);
        setUtterance("");
        if (typeof data.fields.target_concept_id === "number") setTarget(data.fields.target_concept_id);
        if (typeof data.fields.deadline === "string") setDeadline(data.fields.deadline);
        setDailyLimit(typeof data.fields.daily_limit === "number" ? data.fields.daily_limit : null);
        if (data.warnings?.length) toast.push(data.warnings.join("；"), "info");
        if (data.degraded_reason) toast.push("模型不可用，已降级为规则解析", "info");
      },
      onError: (error) => toast.push(error instanceof Error ? error.message : "抽取失败", "error"),
    });
  }

  const summary = preview.data ?? save.data ?? null;
  const course = concepts.data?.items ?? [];

  return (
    <Layout>
      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <section>
            <h2 className="display text-xl">填写约束</h2>
            <p className="faint mt-1 text-xs">
              先用一句话说清楚，系统抽出字段；抽不出的会问，最多问两项。
            </p>
          </section>

          <section className="sheet sheet-pad space-y-3">
            <div className="field-row">
              <label htmlFor="utterance">一句话</label>
              <input
                id="utterance"
                className="input"
                placeholder="我想学指针，10 天后，每天两小时"
                value={utterance}
                onChange={(event) => setUtterance(event.target.value)}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="faint text-xs">
                {modeText ? "解析方式：" + modeText : "规则优先，模型兜底"}
                {dailyLimit ? " · 说到每天 " + dailyLimit + " 分钟" : ""}
              </span>
              <button className="btn" disabled={!utterance || extract.isPending} onClick={runExtract}>
                解析这句话
              </button>
            </div>

            {turns.length ? (
              <div className="space-y-2">
                <p className="faint text-xs">逐轮补全（最多问两项，答不上来就先放下）</p>
                <ul className="space-y-1 text-xs">
                  {turns.map((turn, index) => (
                    <li key={index} className="border-b pb-1" style={{ borderColor: "var(--rule)" }}>
                      <span className="muted">你：{turn.mine}</span>
                      <span className="block" style={{ color: "var(--ink-2)" }}>
                        系统：{turn.reply}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {dailyLimit ? (
              <p className="faint text-xs">
                每日上限已识别为 {dailyLimit} 分钟。本期排程按可用时段总量计算，这一项仅作提醒。
              </p>
            ) : null}

            {questions.length ? (
              <ul className="rule-bottom space-y-1 pb-2 text-sm" style={{ color: "var(--rust)" }}>
                {questions.map((question) => (
                  <li key={question}>还差一点：{question}</li>
                ))}
              </ul>
            ) : null}

            {candidates.length ? (
              <div className="text-sm">
                <p className="faint text-xs">没匹配到唯一知识点，选一个：</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {candidates.map((item) => (
                    <button key={item.concept_id} className="btn btn-quiet"
                            onClick={() => setTarget(item.concept_id)}>
                      {item.name}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </section>

          <section className="sheet sheet-pad">
            <div className="field-row">
              <label htmlFor="target">主目标</label>
              <select id="target" className="input" value={target}
                      onChange={(event) => setTarget(event.target.value === "" ? "" : Number(event.target.value))}>
                <option value="">请选择</option>
                {course.filter((item) => item.status === "enabled").map((item) => (
                  <option key={item.concept_id} value={item.concept_id}>
                    {item.name}（{item.reference_minutes} 分钟，{item.chapter}）
                  </option>
                ))}
              </select>
            </div>
            <div className="field-row">
              <label htmlFor="deadline">截止日期</label>
              <input id="deadline" type="date" className="input num" value={deadline}
                     onChange={(event) => setDeadline(event.target.value)} />
            </div>
            <div className="field-row">
              <label htmlFor="excluded">排除日期</label>
              <input id="excluded" className="input" placeholder="2026-11-15, 2026-11-16"
                     value={excludedText} onChange={(event) => setExcludedText(event.target.value)} />
            </div>
          </section>

          <section className="sheet sheet-pad">
            <h3 className="display text-sm">每周可用时间</h3>
            <p className="faint mt-1 mb-3 text-xs">
              点亮格子即可。每天最多三段、合计不超过八小时。
            </p>
            <div className="avail-grid">
              <div />
              {DAY_LABEL.map((label) => (
                <div key={label} className="tt-head" style={{ padding: "4px 0" }}>
                  周{label}
                </div>
              ))}
              {HOURS.map((hour) => (
                <Row key={hour} hour={hour} cells={cells} onToggle={toggle} />
              ))}
            </div>
          </section>

          <section className="sheet sheet-pad">
            <h3 className="display text-sm">已经会的知识点</h3>
            <p className="faint mt-1 mb-2 text-xs">
              勾上就不再排任务，也不计入目标路径时长；先修内容也可以勾。
            </p>
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              {course.map((item) => (
                <label key={item.concept_id} className="flex items-center gap-1.5 text-sm">
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
          </section>

          <div className="flex items-center gap-3">
            {plan ? null : (
              <button className="btn" disabled={createPlan.isPending}
                      onClick={() =>
                        createPlan.mutate(1, {
                          onSuccess: () => toast.push("学习计划已创建", "success"),
                          onError: (error) =>
                            toast.push(error instanceof Error ? error.message : "创建失败", "error"),
                        })
                      }>
                先创建学习计划
              </button>
            )}
            <button className="btn btn-quiet" disabled={preview.isPending || !plan}
                    onClick={() => preview.mutate(payload, {
                      onError: (error) =>
                        toast.push(error instanceof Error ? error.message : "预览失败", "error"),
                    })}>
              预览容量
            </button>
            <button className="btn" disabled={save.isPending || !plan}
                    onClick={() => save.mutate(payload, {
                      onSuccess: () => toast.push("约束已保存", "success"),
                      onError: (error) =>
                        toast.push(error instanceof Error ? error.message : "保存失败", "error"),
                    })}>
              保存约束
            </button>
          </div>

          <ErrorBox error={preview.error ?? save.error} />
        </div>

        <aside className="space-y-4">
          <section className="sheet sheet-pad">
            <h3 className="display text-sm">容量</h3>
            {summary ? (
              <>
                <dl className="mt-2">
                  <SumRow label="原始容量 C" value={formatMinutes(summary.C)} />
                  <SumRow label="缓冲 B" value={formatMinutes(summary.B)} />
                  <SumRow label="可排 C′" value={formatMinutes(summary.C_prime)} />
                  <SumRow label="目标路径" value={formatMinutes(summary.path_minutes)} />
                  <SumRow label="可用时段" value={summary.slots + " 段"} />
                </dl>
                {summary.reject_reason ? (
                  <p className="mt-2 text-sm" style={{ color: "var(--rust)" }}>
                    排不下：{summary.reject_reason}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="faint mt-2 text-xs">填完点「预览容量」，这里给出 C / B / C′。</p>
            )}
          </section>

          <section className="sheet sheet-pad">
            <h3 className="display text-sm">怎么算的</h3>
            <p className="muted mt-2 text-xs leading-relaxed">
              C 是截止前所有可用时段之和；B 取 C 的 10% 作为缓冲；C′ = C − B 才是能排的上限。
              目标路径只统计闭包内还没掌握的知识点。
            </p>
          </section>
        </aside>
      </div>
    </Layout>
  );
}

function Row({ hour, cells, onToggle }: {
  hour: number; cells: Set<string>; onToggle: (day: string, hour: number) => void;
}) {
  return (
    <>
      <div className="tt-hour-label" style={{ position: "static", textAlign: "right", paddingRight: 4 }}>
        {String(hour).padStart(2, "0")}
      </div>
      {DAY_KEYS.map((day) => (
        <button
          key={day + hour}
          className="avail-cell"
          data-on={cells.has(cellId(day, hour))}
          aria-label={day + " " + hour + " 点"}
          onClick={() => onToggle(day, hour)}
        />
      ))}
    </>
  );
}

function SumRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b py-1.5" style={{ borderColor: "var(--rule)" }}>
      <dt className="muted text-xs">{label}</dt>
      <dd className="num text-sm">{value}</dd>
    </div>
  );
}
