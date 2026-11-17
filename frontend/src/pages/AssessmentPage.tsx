import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { useAuth } from "../hooks/useAuth";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { Card, CardHead, Icon } from "../components/ui";
import {
  useApplyAssessment, useAssessmentItems, useAssessments, useConcepts, useCourses, useCurrentPlan,
  useGenerateAssessment, usePublishAssessment, useSubmitAssessment,
} from "../hooks/queries";

export function AssessmentPage() {
  const toast = useToast();
  const plan = useCurrentPlan().plan;
  const planId = plan?.plan_id ?? 0;
  const list = useAssessments(plan?.course_id ?? 0);
  const [active, setActive] = useState<{ paperId: number; title: string } | null>(null);
  const items = useAssessmentItems(active?.paperId ?? 0);
  const submit = useSubmitAssessment(active?.paperId ?? 0);
  const apply = useApplyAssessment(planId);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [genConceptId, setGenConceptId] = useState(0);
  const { me } = useAuth();
  const isAdmin = me?.role === "admin";
  const courses = useCourses().data?.items ?? [];
  const [adminCourseId, setAdminCourseId] = useState(0);
  const courseId = isAdmin
    ? adminCourseId || courses.find((item) => item.status === "enabled")?.course_id || 0
    : plan?.course_id ?? 0;
  const concepts = useConcepts(courseId).data?.items ?? [];
  const generate = useGenerateAssessment();
  const publish = usePublishAssessment(courseId);

  const papers = list.data?.items ?? [];
  const submitted = submit.data;

  const answeredCount = useMemo(
    () => Object.values(answers).filter((v) => v.trim()).length,
    [answers],
  );

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">课程测评</h1>
          <p className="sub">
            {plan?.course_name ?? "我的课程"} · 管理员发布的测评，提交后给出判分与可解释报告
          </p>
        </div>
        {isAdmin ? (
          <div className="page-head-actions">
            <select className="select" value={courseId}
                    aria-label="选择课程"
                    onChange={(event) => {
                      setAdminCourseId(Number(event.target.value));
                      setGenConceptId(0);
                    }}>
              {courses.map((item) => (
                <option key={item.course_id} value={item.course_id}>
                  {item.name}（{item.semester}）
                </option>
              ))}
            </select>
            <select className="select" value={genConceptId}
                    onChange={(event) => setGenConceptId(Number(event.target.value))}>
              <option value={0}>选择知识点</option>
              {concepts.map((item) => (
                <option key={item.concept_id} value={item.concept_id}>
                  {item.name}{item.outline ? "" : "（缺要点）"}
                </option>
              ))}
            </select>
            <button className="btn btn-ghost"
                    disabled={!genConceptId || generate.isPending}
                    onClick={() =>
                      generate.mutate(genConceptId, {
                        onSuccess: () => toast.push("已生成草稿，请检查后发布", "success"),
                        onError: (error) =>
                          toast.push(error instanceof Error ? error.message : "生成失败", "error"),
                      })}>
              {generate.isPending ? "出题中…" : "AI 出题"}
            </button>
          </div>
        ) : null}
      </header>

      <div className="stack">
        <ErrorBox error={list.error ?? items.error ?? submit.error} />

        {!plan ? (
          <Card>
            <div className="card-body">
              <p className="sub">还没有学习计划，先去「学习偏好」选一门课。</p>
              <Link className="btn" to="/constraint" style={{ marginTop: 10 }}>
                <Icon name="plus" />制定计划
              </Link>
            </div>
          </Card>
        ) : null}

        {plan && !papers.length ? (
          <Card>
            <CardHead title="暂无已发布的测评" hint="等管理员发布后即可在这里作答" />
          </Card>
        ) : null}

        {isAdmin && generate.data ? (
          <Card>
            <CardHead
              title={generate.data.title}
              hint={"AI 出题草稿 · " + generate.data.items.length + " 题（含答案键，发布后学生看不到答案）"}
              action={
                <button className="btn btn-sm"
                        disabled={publish.isPending}
                        onClick={() =>
                          publish.mutate(generate.data!.paper_id, {
                            onSuccess: () => {
                              toast.push("已发布，学生端可见", "success");
                              list.refetch();
                            },
                            onError: (error) =>
                              toast.push(error instanceof Error ? error.message : "发布失败", "error"),
                          })}>
                  发布
                </button>
              }
            />
            <div className="card-body stack" style={{ gap: 10 }}>
              {generate.data.items.map((item) => (
                <div key={item.no}>
                  <p className="row-title" style={{ fontSize: 13 }}>
                    {item.no}. {item.stem}（{item.points} 分）
                  </p>
                  {item.type === "single" && item.options ? (
                    <p className="row-sub">选项：{item.options.join(" / ")}</p>
                  ) : (
                    <p className="row-sub">简答题：按采分点判分</p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        {papers.length ? (
          <Card>
            <CardHead title={"测评（" + papers.length + "）"} hint="点击开始作答" />
            <div className="card-body stack" style={{ gap: 10 }}>
              {papers.map((paper) => (
                <div key={paper.paper_id} className="admin-inline"
                     style={{ justifyContent: "space-between" }}>
                  <div>
                    <p className="row-title" style={{ fontSize: 14 }}>{paper.title}</p>
                    <p className="row-sub">{paper.count} 道题 · 发布于 {paper.published_at ?? "—"}</p>
                  </div>
                  <button className="btn btn-ghost"
                          onClick={() => {
                            setAnswers({});
                            setActive({ paperId: paper.paper_id, title: paper.title });
                            submit.reset();
                          }}>
                    开始作答
                  </button>
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        {active && items.data ? (
          <Card>
            <CardHead
              title={active.title}
              hint={"已作答 " + answeredCount + " / " + items.data.items.length}
              action={<button className="link-btn" onClick={() => setActive(null)}>关闭</button>}
            />
            <div className="card-body stack" style={{ gap: 14 }}>
              {items.data.items.map((item) => (
                <div key={item.no}>
                  <p className="row-title" style={{ fontSize: 13.5 }}>
                    {item.no}. {item.stem}
                    <span className="row-sub"> （{item.points} 分）</span>
                  </p>
                  {item.type === "single" ? (
                    <div className="stack" style={{ gap: 6, marginTop: 8 }}>
                      {(item.options ?? []).map((option, index) => {
                        const letter = "ABCD"[index];
                        return (
                          <label key={letter} className="admin-inline" style={{ gap: 8 }}>
                            <input
                              type="radio"
                              name={"q" + item.no}
                              value={letter}
                              checked={answers[String(item.no)] === letter}
                              onChange={() =>
                                setAnswers((prev) => ({ ...prev, [String(item.no)]: letter }))}
                            />
                            <span>{letter}. {option}</span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <textarea
                      className="input"
                      style={{ marginTop: 8, minHeight: 72 }}
                      placeholder="用几句话写清你的理解（按采分点给分）"
                      value={answers[String(item.no)] ?? ""}
                      onChange={(event) =>
                        setAnswers((prev) => ({ ...prev, [String(item.no)]: event.target.value }))}
                    />
                  )}
                </div>
              ))}
              <div className="admin-inline">
                <button className="btn"
                        disabled={submit.isPending || answeredCount === 0}
                        onClick={() =>
                          submit.mutate(answers, {
                            onSuccess: () => toast.push("已提交并完成判分", "success"),
                            onError: (error) =>
                              toast.push(error instanceof Error ? error.message : "提交失败", "error"),
                          })}>
                  {submit.isPending ? "判分中…" : "提交并看报告"}
                </button>
              </div>
            </div>
          </Card>
        ) : null}

        {submitted ? (
          <Card>
            <CardHead
              title="测评报告"
              hint={submitted.status === "manual_review"
                ? "部分题目待人工复核，分数暂按程序重算"
                : "分数由程序重算，解释由模型生成"}
              action={
                <span className="chip" data-tone={submitted.score / submitted.max_score >= 0.8 ? "done" : "warn"}>
                  {submitted.score} / {submitted.max_score}
                </span>
              }
            />
            <div className="card-body stack" style={{ gap: 12 }}>
              {submitted.report.items.map((detail) => (
                <div key={detail.no} className="issue-row"
                     data-level={detail.got === detail.points ? "INFO" : "WARN"}>
                  <span className="issue-code">
                    Q{detail.no} {detail.got}/{detail.points}
                  </span>
                  <span>
                    {detail.hits.length ? <>命中：{detail.hits.join("；")}</> : "未命中采分点"}
                    {detail.misses.length ? (
                      <span className="row-sub" style={{ display: "block" }}>
                        还缺：{detail.misses.join("；")}
                      </span>
                    ) : null}
                    {detail.quotes.length ? (
                      <span className="row-sub" style={{ display: "block" }}>
                        依据原文：{detail.quotes.join(" / ")}
                      </span>
                    ) : null}
                    {detail.review_flag ? (
                      <span className="chip" data-tone="warn" style={{ marginTop: 6 }}>
                        待人工复核
                      </span>
                    ) : null}
                  </span>
                </div>
              ))}
              <p className="row-title" style={{ fontSize: 13.5 }}>
                结论：{submitted.report.suggestion}
              </p>
              {submitted.report.weak_points.length ? (
                <p className="row-sub">薄弱点：{submitted.report.weak_points.join("；")}</p>
              ) : null}
              {submitted.report.action === "mark_mastered" ? (
                <div className="admin-inline">
                  <button className="btn"
                          disabled={apply.isPending}
                          onClick={() =>
                            apply.mutate(submitted.attempt_id, {
                              onSuccess: () => toast.push("已标记为已掌握，重排后生效", "success"),
                              onError: (error) =>
                                toast.push(error instanceof Error ? error.message : "操作失败", "error"),
                            })}>
                    采纳建议：标记为已掌握
                  </button>
                  <span className="row-sub">重排计划后该知识点不再占用时间</span>
                </div>
              ) : null}
            </div>
          </Card>
        ) : null}
      </div>
    </Layout>
  );
}
