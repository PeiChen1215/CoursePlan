import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import { Card, CardHead, Field } from "../components/ui";
import {
  useConcepts, useCourses, useCreateConcept, useCreateResource, useDisableCourse,
  useDisableResource, usePatchCourse, usePrereqs, useResources, useSetConceptResources,
  useSubmitPrereqs,
} from "../hooks/queries";

export function AdminPage() {
  const toast = useToast();
  const courseId = 1;
  const courses = useCourses();
  const concepts = useConcepts(courseId);
  const prereqs = usePrereqs(courseId);
  const createConcept = useCreateConcept(courseId);
  const submitPrereqs = useSubmitPrereqs(courseId);
  const patchCourse = usePatchCourse();
  const disableCourse = useDisableCourse();

  const course = courses.data?.items?.find((item) => item.course_id === courseId) ?? null;

  const [courseName, setCourseName] = useState("");
  const [courseHours, setCourseHours] = useState("");
  const [name, setName] = useState("");
  const [chapter, setChapter] = useState("第1章");
  const [difficulty, setDifficulty] = useState(3);
  const [minutes, setMinutes] = useState(60);
  const [fromId, setFromId] = useState<number | "">("");
  const [toId, setToId] = useState<number | "">("");

  const resources = useResources(courseId);
  const createResource = useCreateResource(courseId);
  const disableResource = useDisableResource(courseId);
  const setConceptResources = useSetConceptResources(courseId);
  const [resTitle, setResTitle] = useState("");
  const [resType, setResType] = useState("document");
  const [resUrl, setResUrl] = useState("");
  const [resSummary, setResSummary] = useState("");
  const [resMinutes, setResMinutes] = useState(0);
  const [linkTarget, setLinkTarget] = useState<number | "">("");
  const [linkIds, setLinkIds] = useState<number[]>([]);

  const list = concepts.data?.items ?? [];
  const edges = prereqs.data?.items ?? [];
  const byId = new Map(list.map((item) => [item.concept_id, item.name]));

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">课程内容</h1>
          <p className="sub">
            先修关系整批提交：成环时整批拒绝并返回环路；被版本引用的知识点只能停用。
          </p>
        </div>
        {course ? (
          <span className="chip" data-tone={course.status === "enabled" ? "done" : "warn"}>
            {course.status === "enabled" ? "启用中" : "已停用"}
          </span>
        ) : null}
      </header>

      <div className="stack">
        <Card>
          <CardHead title="课程信息" hint={course?.semester ?? ""} />
          <div className="card-body">
            <div className="grid-3" style={{ gridTemplateColumns: "1.2fr 0.6fr auto", gap: 12, alignItems: "end" }}>
              <Field label="课程名称">
                <input className="input" placeholder={course?.name ?? ""} value={courseName}
                       onChange={(event) => setCourseName(event.target.value)} />
              </Field>
              <Field label="总学时">
                <input className="input num" placeholder={course ? String(course.total_hours) : ""}
                       value={courseHours} inputMode="numeric"
                       onChange={(event) => setCourseHours(event.target.value)} />
              </Field>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn"
                  disabled={patchCourse.isPending || (!courseName && !courseHours)}
                  onClick={() => {
                    const patch: Record<string, unknown> = {};
                    if (courseName) patch.name = courseName;
                    if (courseHours) patch.total_hours = Number(courseHours);
                    patchCourse.mutate({ courseId, patch }, {
                      onSuccess: () => {
                        toast.push("课程信息已更新", "success");
                        setCourseName("");
                        setCourseHours("");
                      },
                      onError: (error) =>
                        toast.push(error instanceof Error ? error.message : "更新失败", "error"),
                    });
                  }}
                >
                  保存
                </button>
                <button
                  className="btn btn-ghost"
                  disabled={disableCourse.isPending || course?.status === "disabled"}
                  onClick={() => {
                    if (!window.confirm("停用后无法新建学习计划，历史计划仍可打开。确认停用？")) return;
                    disableCourse.mutate(courseId, {
                      onSuccess: () => toast.push("课程已停用", "success"),
                      onError: (error) =>
                        toast.push(error instanceof Error ? error.message : "停用失败", "error"),
                    });
                  }}
                >
                  停用课程
                </button>
              </div>
            </div>
          </div>
        </Card>

        <ErrorBox error={patchCourse.error ?? disableCourse.error} />

        <Card>
          <CardHead title={"知识点（" + list.length + "）"} hint="按章节顺序排列" />
          <div className="card-body" style={{ paddingTop: 0, paddingLeft: 8, paddingRight: 8 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th><th>名称</th><th>章节</th><th>难度</th><th>时长</th><th>状态</th>
                </tr>
              </thead>
              <tbody>
                {list.map((item) => (
                  <tr key={item.concept_id}>
                    <td className="num row-sub">{item.concept_id}</td>
                    <td style={{ fontWeight: 550 }}>{item.name}</td>
                    <td className="row-sub">{item.chapter}</td>
                    <td className="num">{item.difficulty}</td>
                    <td className="num">{item.reference_minutes} 分</td>
                    <td>
                      <span className="chip" data-tone={item.status === "enabled" ? "done" : "warn"}>
                        {item.status === "enabled" ? "启用" : "停用"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="grid-2">
          <Card>
            <CardHead title="新增知识点" />
            <div className="card-body stack" style={{ gap: 12 }}>
              <Field label="名称">
                <input className="input" value={name} onChange={(event) => setName(event.target.value)} />
              </Field>
              <div className="grid-2" style={{ gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                <Field label="章节">
                  <input className="input" value={chapter} onChange={(event) => setChapter(event.target.value)} />
                </Field>
                <Field label="难度">
                  <input className="input num" type="number" min={1} max={5} value={difficulty}
                         onChange={(event) => setDifficulty(Number(event.target.value))} />
                </Field>
                <Field label="参考时长">
                  <input className="input num" type="number" min={5} max={600} value={minutes}
                         onChange={(event) => setMinutes(Number(event.target.value))} />
                </Field>
              </div>
              <button className="btn" disabled={!name || createConcept.isPending}
                      onClick={() => createConcept.mutate(
                        { name, chapter, difficulty, reference_minutes: minutes },
                        {
                          onSuccess: () => {
                            toast.push("已新增知识点", "success");
                            setName("");
                          },
                          onError: (error) =>
                            toast.push(error instanceof Error ? error.message : "新增失败", "error"),
                        },
                      )}>
                新增
              </button>
            </div>
          </Card>

          <Card>
            <CardHead title={"先修关系（" + edges.length + "）"} hint="先修 → 后继" />
            <div className="card-body stack" style={{ gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <select className="select" value={fromId}
                        onChange={(event) => setFromId(event.target.value === "" ? "" : Number(event.target.value))}>
                  <option value="">先修</option>
                  {list.map((item) => (
                    <option key={item.concept_id} value={item.concept_id}>{item.name}</option>
                  ))}
                </select>
                <span className="faint">→</span>
                <select className="select" value={toId}
                        onChange={(event) => setToId(event.target.value === "" ? "" : Number(event.target.value))}>
                  <option value="">后继</option>
                  {list.map((item) => (
                    <option key={item.concept_id} value={item.concept_id}>{item.name}</option>
                  ))}
                </select>
                <button className="btn" disabled={fromId === "" || toId === "" || submitPrereqs.isPending}
                        onClick={() => submitPrereqs.mutate([[Number(fromId), Number(toId)]], {
                          onSuccess: (data) => toast.push("已保存 " + data.saved + " 条", "success"),
                          onError: (error) =>
                            toast.push(error instanceof Error ? error.message : "提交失败", "error"),
                        })}>
                  提交
                </button>
              </div>
              <div style={{ maxHeight: 210, overflowY: "auto" }}>
                {edges.map((edge) => (
                  <div key={edge.from_concept_id + "-" + edge.to_concept_id} className="row-item" style={{ padding: "6px 0" }}>
                    <span className="row-sub">
                      {byId.get(edge.from_concept_id) ?? edge.from_concept_id} →{" "}
                      {byId.get(edge.to_concept_id) ?? edge.to_concept_id}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>

        <Card>
          <CardHead
            title={"课程资料（" + (resources.data?.items.length ?? 0) + "）"}
            hint="资料只有关联到知识点，学生才会在任务里看到"
          />
          <div className="card-body stack" style={{ gap: 12 }}>
            <div className="grid-3" style={{ gridTemplateColumns: "1.4fr 0.8fr 1.6fr 0.6fr", gap: 10 }}>
              <Field label="标题">
                <input className="input" value={resTitle} onChange={(event) => setResTitle(event.target.value)} />
              </Field>
              <Field label="类型">
                <select className="select" value={resType} onChange={(event) => setResType(event.target.value)}>
                  <option value="document">文档</option>
                  <option value="video">视频</option>
                  <option value="exercise">练习</option>
                  <option value="link">链接</option>
                </select>
              </Field>
              <Field label="网址">
                <input className="input" placeholder="https://…" value={resUrl}
                       onChange={(event) => setResUrl(event.target.value)} />
              </Field>
              <Field label="分钟">
                <input className="input num" type="number" min={0} max={240} value={resMinutes}
                       onChange={(event) => setResMinutes(Number(event.target.value))} />
              </Field>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
              <div className="field" style={{ flex: 1 }}>
                <label>摘要（没网址时必填）</label>
                <input className="input" value={resSummary}
                       onChange={(event) => setResSummary(event.target.value)} />
              </div>
              <button className="btn" disabled={!resTitle || createResource.isPending}
                      onClick={() => createResource.mutate(
                        { title: resTitle, type: resType, url: resUrl || undefined,
                          summary: resSummary || undefined, read_minutes: resMinutes },
                        {
                          onSuccess: () => {
                            toast.push("资料已新增", "success");
                            setResTitle(""); setResUrl(""); setResSummary(""); setResMinutes(0);
                          },
                          onError: (error) =>
                            toast.push(error instanceof Error ? error.message : "新增失败", "error"),
                        },
                      )}>
                新增资料
              </button>
            </div>

            <table className="table">
              <thead>
                <tr><th>标题</th><th>类型</th><th>链接</th><th>分钟</th><th>状态</th><th /></tr>
              </thead>
              <tbody>
                {(resources.data?.items ?? []).map((item) => (
                  <tr key={item.resource_id}>
                    <td>
                      <span style={{ fontWeight: 550 }}>{item.title}</span>
                      {item.summary ? <span className="row-sub" style={{ display: "block" }}>{item.summary}</span> : null}
                    </td>
                    <td><span className="chip" data-tone="brand">{item.type_label}</span></td>
                    <td className="row-sub">
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noreferrer" className="link-btn"
                           style={{ fontSize: 12 }}>
                          {item.url.slice(0, 26)}…
                        </a>
                      ) : "—"}
                    </td>
                    <td className="num">{item.read_minutes}</td>
                    <td>
                      <span className="chip" data-tone={item.status === "enabled" ? "done" : "warn"}>
                        {item.status === "enabled" ? "启用" : "停用"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 10 }}>
                        <button
                          className="link-btn"
                          style={{ fontSize: 12 }}
                          onClick={() => setLinkIds((prev) =>
                            prev.includes(item.resource_id)
                              ? prev.filter((id) => id !== item.resource_id)
                              : [...prev, item.resource_id])}
                        >
                          {linkIds.includes(item.resource_id) ? "已选中" : "选中"}
                        </button>
                        <button
                          className="link-btn"
                          style={{ fontSize: 12, color: "var(--danger)" }}
                          disabled={item.status === "disabled" || disableResource.isPending}
                          onClick={() => disableResource.mutate(item.resource_id, {
                            onSuccess: (data) =>
                              toast.push("已停用，解除了 " + data.linked_concepts + " 处关联", "success"),
                            onError: (error) =>
                              toast.push(error instanceof Error ? error.message : "停用失败", "error"),
                          })}
                        >
                          停用
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {(resources.data?.items ?? []).length === 0 ? (
                  <tr><td colSpan={6} className="row-sub" style={{ textAlign: "center", padding: 18 }}>
                    还没有资料
                  </td></tr>
                ) : null}
              </tbody>
            </table>

            <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
              <div className="field" style={{ width: 240 }}>
                <label>关联到知识点</label>
                <select className="select" value={linkTarget}
                        onChange={(event) => setLinkTarget(event.target.value === "" ? "" : Number(event.target.value))}>
                  <option value="">请选择</option>
                  {list.map((item) => (
                    <option key={item.concept_id} value={item.concept_id}>{item.name}</option>
                  ))}
                </select>
              </div>
              <button className="btn btn-ghost" disabled={linkTarget === "" || setConceptResources.isPending}
                      onClick={() => setConceptResources.mutate(
                        { conceptId: Number(linkTarget), ids: linkIds },
                        {
                          onSuccess: (data) => toast.push("已关联 " + data.linked + " 条资料", "success"),
                          onError: (error) =>
                            toast.push(error instanceof Error ? error.message : "关联失败", "error"),
                        },
                      )}>
                保存关联
              </button>
              <span className="row-sub">已选 {linkIds.length} 条</span>
            </div>
          </div>
        </Card>

        <ErrorBox error={createConcept.error ?? submitPrereqs.error ?? createResource.error} />
      </div>
    </Layout>
  );
}
