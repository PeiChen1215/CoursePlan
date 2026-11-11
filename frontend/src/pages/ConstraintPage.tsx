import { useEffect, useMemo, useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { Card, CardHead, Field, Icon } from "../components/ui";
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
  const totalCells = cells.size;

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">学习偏好</h1>
          <p className="sub">{plan?.course_name ?? "我的课程"} · 目标、期限与学习时间</p>
        </div>
        <div className="page-head-actions">
          {plan ? null : (
            <button className="btn btn-ghost" disabled={createPlan.isPending}
                    onClick={() =>
                      createPlan.mutate(1, {
                        onSuccess: () => toast.push("学习计划已创建", "success"),
                        onError: (error) =>
                          toast.push(error instanceof Error ? error.message : "创建失败", "error"),
                      })
                    }>
              创建学习计划
            </button>
          )}
          <button className="btn btn-ghost" disabled={preview.isPending || !plan}
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
      </header>

      <div className="grid-2">
        <div className="stack">
          <Card>
            <CardHead
              title="用一句话描述"
              hint={extract.isPending ? "正在整理…" : undefined}
            />
            <div className="card-body">
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  className="input"
                  name="utterance"
                  aria-label="用一句话描述目标、期限和可用时间"
                  placeholder="例如：12 月前学完单元测试，每周一、三晚上学习"
                  value={utterance}
                  onChange={(event) => setUtterance(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && utterance && !extract.isPending) runExtract();
                  }}
                />
                <button className="btn" disabled={!utterance || extract.isPending} onClick={runExtract}>
                  解析
                </button>
              </div>

              {turns.length ? (
                <div className="stack" style={{ gap: 8, marginTop: 14 }}>
                  {turns.map((turn, index) => (
                    <div key={index} className="card card-quiet card-pad" style={{ padding: "10px 12px" }}>
                      <p className="row-sub">你：{turn.mine}</p>
                      <p style={{ fontSize: 13, marginTop: 2 }}>{turn.reply}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              {candidates.length ? (
                <div style={{ marginTop: 12 }}>
                  <p className="field-hint">没匹配到唯一知识点，选一个：</p>
                  <div className="tag-list" style={{ marginTop: 6 }}>
                    {candidates.map((item) => (
                      <button key={item.concept_id} className="chip" data-tone="brand"
                              style={{ border: 0, cursor: "pointer", height: 26 }}
                              onClick={() => setTarget(item.concept_id)}>
                        {item.name}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {questions.length ? (
                <p className="field-hint" style={{ marginTop: 10, color: "var(--warn)" }}>
                  还需要：{questions.join("；")}
                </p>
              ) : null}

              {dailyLimit ? (
                <p className="field-hint" style={{ marginTop: 8 }}>
                  每日上限识别为 {dailyLimit} 分钟（本期按可用时段总量计算，此项仅作提醒）。
                </p>
              ) : null}
            </div>
          </Card>

          <Card>
            <CardHead title="目标与期限" />
            <div className="card-body stack" style={{ gap: 14 }}>
              <Field label="主目标">
                <select className="select" value={target}
                        onChange={(event) => setTarget(event.target.value === "" ? "" : Number(event.target.value))}>
                  <option value="">请选择</option>
                  {course.filter((item) => item.status === "enabled").map((item) => (
                    <option key={item.concept_id} value={item.concept_id}>
                      {item.name}（{item.reference_minutes} 分钟 · {item.chapter}）
                    </option>
                  ))}
                </select>
              </Field>
              <div className="grid-3" style={{ gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Field label="截止日期">
                  <input type="date" className="input num" value={deadline}
                         onChange={(event) => setDeadline(event.target.value)} />
                </Field>
                <Field label="排除日期" hint="逗号分隔，如 2026-11-15">
                  <input className="input" placeholder="2026-11-15, 2026-11-16"
                         value={excludedText} onChange={(event) => setExcludedText(event.target.value)} />
                </Field>
              </div>
            </div>
          </Card>

          <Card>
            <CardHead
              title="每周可用时间"
              hint="点亮格子即可，每天最多三段"
              action={<span className="chip" data-tone="brand">{totalCells} 小时</span>}
            />
            <div className="card-body">
              <div className="avail">
                <div />
                {DAY_LABEL.map((label) => (
                  <div key={label} className="cal-dow" style={{ textAlign: "center", padding: "6px 0" }}>
                    周{label}
                  </div>
                ))}
                {HOURS.map((hour) => (
                  <Row key={hour} hour={hour} cells={cells} onToggle={toggle} />
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <CardHead title="已经会的知识点" hint="勾上就不再排任务，也不计入目标路径时长" />
            <div className="card-body">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {course.map((item) => (
                  <label key={item.concept_id} className="check" data-on={mastered.includes(item.concept_id)}>
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
          </Card>

          <ErrorBox error={preview.error ?? save.error} />
        </div>

        <div className="stack">
          <Card>
            <CardHead title="容量" hint="C 是截止前所有可用时段之和" />
            <div className="card-body">
              {summary ? (
                <div className="stack" style={{ gap: 10 }}>
                  <div className="stat-strip" style={{ gridTemplateColumns: "1fr 1fr", gap: 1 }}>
                    <div className="stat" style={{ padding: "10px 12px" }}>
                      <p className="stat-label">原始容量 C</p>
                      <p className="stat-value" style={{ fontSize: 17 }}>{formatMinutes(summary.C)}</p>
                    </div>
                    <div className="stat" style={{ padding: "10px 12px" }}>
                      <p className="stat-label">可排 C′</p>
                      <p className="stat-value" style={{ fontSize: 17 }}>{formatMinutes(summary.C_prime)}</p>
                    </div>
                    <div className="stat" style={{ padding: "10px 12px" }}>
                      <p className="stat-label">缓冲 B</p>
                      <p className="stat-value" style={{ fontSize: 17 }}>{formatMinutes(summary.B)}</p>
                    </div>
                    <div className="stat" style={{ padding: "10px 12px" }}>
                      <p className="stat-label">目标路径</p>
                      <p className="stat-value" style={{ fontSize: 17 }}>{formatMinutes(summary.path_minutes)}</p>
                    </div>
                  </div>
                  <p className="field-hint">可用时段 {summary.slots} 段</p>
                  {summary.reject_reason ? (
                    <p className="sub" style={{ color: "var(--danger)" }}>
                      排不下：{summary.reject_reason}
                    </p>
                  ) : (
                    <p className="sub" style={{ color: "var(--done)" }}>时间够用，可以保存并生成草案。</p>
                  )}
                </div>
              ) : (
                <p className="sub">填完点「预览容量」，这里给出 C / B / C′。</p>
              )}
            </div>
          </Card>

          <Card className="card-pad" quiet>
            <div style={{ display: "flex", gap: 10 }}>
              <span className="chip" data-tone="brand"><Icon name="spark" size={12} />怎么算的</span>
            </div>
            <p className="sub" style={{ marginTop: 8 }}>
              C 是截止前所有可用时段之和；B 取 C 的 10% 作为缓冲；C′ = C − B 才是能排的上限。
              目标路径只统计闭包内还没掌握的知识点。
            </p>
          </Card>
        </div>
      </div>
    </Layout>
  );
}

function Row({ hour, cells, onToggle }: {
  hour: number; cells: Set<string>; onToggle: (day: string, hour: number) => void;
}) {
  return (
    <>
      <div className="mono-sm" style={{ display: "grid", placeItems: "center", borderRight: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
        {String(hour).padStart(2, "0")}
      </div>
      {DAY_KEYS.map((day) => {
        const on = cells.has(cellId(day, hour));
        return (
          <button
            key={day + hour}
            type="button"
            className="avail-cell"
            data-on={on}
            aria-pressed={on}
            aria-label={day + " " + hour + " 点" + (on ? "，已选" : "，未选")}
            onClick={() => onToggle(day, hour)}
          />
        );
      })}
    </>
  );
}
