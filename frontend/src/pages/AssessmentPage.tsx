import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { useAuth } from "../hooks/useAuth";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { Card, CardHead, Icon, Stat } from "../components/ui";
import {
  useApplyAssessment, useAssessmentItems, useAssessments, useConcepts, useCourses,
  useCurrentPlan, useGenerateAssessment, usePaperStats, usePublishAssessment,
  useSubmitAssessment,
} from "../hooks/queries";

export function AssessmentPage() {
  const toast = useToast();
  const plan = useCurrentPlan().plan;
  const planId = plan?.plan_id ?? 0;
  const { me } = useAuth();
  const isAdmin = me?.role === "admin";

  const courses = useCourses().data?.items ?? [];
  const [adminCourseId, setAdminCourseId] = useState(0);
  const courseId = isAdmin
    ? adminCourseId || courses.find((item) => item.status === "enabled")?.course_id || 0
    : plan?.course_id ?? 0;

  const concepts = useConcepts(courseId).data?.items ?? [];
  const [genConceptId, setGenConceptId] = useState(0);
  const generate = useGenerateAssessment();
  const publish = usePublishAssessment(courseId);

  const list = useAssessments(courseId);
  const papers = list.data?.items ?? [];

  const [active, setActive] = useState<{ paperId: number; title: string } | null>(null);
  const items = useAssessmentItems(active?.paperId ?? 0);
  const submit = useSubmitAssessment(active?.paperId ?? 0);
  const apply = useApplyAssessment(planId);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const [statsFor, setStatsFor] = useState(0);
  const stats = usePaperStats(statsFor);

  const report = submit.data;
  const answeredCount = useMemo(
    () => Object.values(answers).filter((value) => value.trim()).length,
    [answers],
  );

  const start = (paperId: number, title: string) => {
    setAnswers({});
    setActive({ paperId, title });
    submit.reset();
  };

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">课程测评</h1>
          <p className="sub">
            {isAdmin
              ? "管理员出题与发布 · 查看班级学情"
              : (plan?.course_name ?? "我的课程") + " · 提交后给出判分与可解释报告"}
          </p>
        </div>
        {isAdmin ? (
          <div className="page-head-actions">
            <select className="select" value={courseId} aria-label="选择课程"
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
            <select className="select" value={genConceptId} aria-label="选择知识点"
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

        {!isAdmin && !plan ? (
          <Card>
            <div className="card-body">
              <p className="sub">还没有学习计划，先去「学习偏好」选一门课。</p>
              <Link className="btn" to="/constraint" style={{ marginTop: 10 }}>
                <Icon name="plus" />制定计划
              </Link>
            </div>
          </Card>
        ) : null}

        {isAdmin && generate.data ? (
          <Card>
            <CardHead
              title={generate.data.title}
              hint={"AI 出题草稿 · " + generate.data.items.length + " 题（含答案键，发布后学生看不到）"}
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
                    <p className="row-sub">简答题：由模型按理解是否正确判分</p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        {isAdmin && papers.length ? (
          <Card>
            <CardHead
              title="班级学情"
              hint="按试卷统计作答人数、平均分与逐题得分率"
              action={
                <select className="select" value={statsFor} aria-label="选择试卷"
                        onChange={(event) => setStatsFor(Number(event.target.value))}>
                  <option value={0}>选择试卷</option>
                  {papers.map((paper) => (
                    <option key={paper.paper_id} value={paper.paper_id}>{paper.title}</option>
                  ))}
                </select>
              }
            />
            <div className="card-body stack" style={{ gap: 12 }}>
              {!statsFor ? <p className="sub">选择一套试卷查看学情。</p> : null}
              {stats.data ? (
                <>
                  <div className="stat-strip">
                    <Stat label="作答人数" value={String(stats.data.attempts)} />
                    <Stat label="平均分" value={String(stats.data.average)}
                          unit={" / " + stats.data.max_score} />
                    <Stat label="及格率" value={(stats.data.pass_rate * 100).toFixed(0) + "%"} />
                    <Stat label="最高 / 最低" value={stats.data.highest + " / " + stats.data.lowest} />
                  </div>
                  <div className="table-scroll">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>题号</th><th>题型</th><th>平均得分</th>
                          <th>得分率</th><th>作答数</th><th>待复核</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stats.data.items.map((item) => (
                          <tr key={item.no}>
                            <td className="num">{item.no}</td>
                            <td>{item.type === "single" ? "单选" : "简答"}</td>
                            <td className="num">{item.avg_got} / {item.points}</td>
                            <td className="num">{(item.rate * 100).toFixed(0)}%</td>
                            <td className="num">{item.attempts}</td>
                            <td className="num">{item.review_flags}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="row-sub">
                    分数分布：
                    {["<50%", "50-70%", "70-85%", ">=85%"].map((key) =>
                      key + " " + (stats.data!.distribution[key] ?? 0) + " 人").join(" · ")}
                  </p>
                  {stats.data.recent.length ? (
                    <p className="row-sub">
                      最近提交：
                      {stats.data.recent.slice(0, 5).map((row) =>
                        row.username + " " + row.score + "/" + row.max_score).join(" · ")}
                    </p>
                  ) : (
                    <p className="row-sub">还没有人作答。</p>
                  )}
                </>
              ) : null}
            </div>
          </Card>
        ) : null}

        {(isAdmin || plan) && !papers.length ? (
          <Card>
            <CardHead title="暂无已发布的测评" hint="等管理员发布后即可在这里作答" />
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
                    <p className="row-sub">
                      {paper.count} 道题 · 发布于 {paper.published_at ?? "—"}
                    </p>
                  </div>
                  <button className="btn btn-ghost"
                          onClick={() => start(paper.paper_id, paper.title)}>
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
                      placeholder="用几句话写清你的理解（模型按理解是否正确判分）"
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

        {report ? (
          <Card>
            <CardHead
              title="测评报告"
              hint={report.status === "manual_review"
                ? "部分题目待人工复核，分数按已判出结果暂计"
                : "选择题程序判分 · 简答题模型判分（附理由）"}
              action={
                <span className="chip"
                      data-tone={report.score / report.max_score >= 0.6 ? "done" : "warn"}>
                  {report.score} / {report.max_score}
                </span>
              }
            />
            <div className="card-body stack" style={{ gap: 4 }}>
              <p className="row-sub">
                得分率 {(report.report.ratio * 100).toFixed(0)}% ·
                {report.report.ratio >= 0.6 ? " 达到及格线" : " 未达及格线"} ·
                共 {report.report.items.length} 题
              </p>

              {report.report.items.map((detail) => {
                const perfect = detail.got === detail.points;
                return (
                  <div key={detail.no} className="report-item">
                    <div className="report-head">
                      <span className="chip" data-tone={perfect ? "done" : "warn"}>
                        Q{detail.no} {detail.got}/{detail.points}
                      </span>
                      <span className="row-sub">
                        {detail.type === "single" ? "单选" : "简答"}
                      </span>
                      {detail.review_flag ? (
                        <span className="chip" data-tone="warn">待人工复核</span>
                      ) : null}
                    </div>

                    {detail.stem ? <p className="report-stem">{detail.stem}</p> : null}

                    {detail.type === "single" ? (
                      <>
                        <p className="report-line">
                          <span className="row-sub">你的选择：</span>
                          {detail.chosen
                            ? detail.chosen + (detail.chosen_text ? ". " + detail.chosen_text : "")
                            : "（未作答）"}
                        </p>
                        <p className="report-line">
                          <span className="row-sub">正确答案：</span>
                          {detail.answer}
                          {detail.answer_text ? ". " + detail.answer_text : ""}
                        </p>
                      </>
                    ) : (
                      <p className="report-line">
                        <span className="row-sub">你的作答：</span>
                        {detail.chosen || "（未作答）"}
                      </p>
                    )}

                    {detail.reason ? (
                      <p className="report-line">
                        <span className="row-sub">判分理由：</span>
                        {detail.reason}
                      </p>
                    ) : null}

                    {detail.rubric && detail.rubric.length ? (
                      <p className="report-line">
                        <span className="row-sub">要点：</span>
                        {detail.rubric.join("；")}
                      </p>
                    ) : null}

                    {detail.quotes && detail.quotes.length ? (
                      <p className="report-line">
                        <span className="row-sub">引用原话：</span>
                        {detail.quotes.join(" / ")}
                      </p>
                    ) : null}
                  </div>
                );
              })}

              <p className="row-title" style={{ fontSize: 13.5, marginTop: 10 }}>
                结论：{report.report.suggestion}
              </p>
              {report.report.weak_points.length ? (
                <p className="row-sub">薄弱点：{report.report.weak_points.join("；")}</p>
              ) : null}
              {report.report.action === "mark_mastered" ? (
                <div className="admin-inline" style={{ marginTop: 8 }}>
                  <button className="btn"
                          disabled={apply.isPending}
                          onClick={() =>
                            apply.mutate(report.attempt_id, {
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
