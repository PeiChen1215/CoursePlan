import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import {
  useConcepts, useCourses, useCreateConcept, useDisableCourse, usePatchCourse, usePrereqs,
  useSubmitPrereqs,
} from "../hooks/queries";

export function AdminPage() {
  const toast = useToast();
  const courseId = 1;
  const courses = useCourses();
  const patchCourse = usePatchCourse();
  const disableCourse = useDisableCourse();
  const course = courses.data?.items?.find((item) => item.course_id === courseId) ?? null;
  const [courseName, setCourseName] = useState("");
  const [courseHours, setCourseHours] = useState("");

  const concepts = useConcepts(courseId);
  const prereqs = usePrereqs(courseId);
  const createConcept = useCreateConcept(courseId);
  const submitPrereqs = useSubmitPrereqs(courseId);

  const [name, setName] = useState("");
  const [chapter, setChapter] = useState("第1章");
  const [difficulty, setDifficulty] = useState(3);
  const [minutes, setMinutes] = useState(60);
  const [fromId, setFromId] = useState<number | "">("");
  const [toId, setToId] = useState<number | "">("");

  const list = concepts.data?.items ?? [];
  const edges = prereqs.data?.items ?? [];
  const byId = new Map(list.map((item) => [item.concept_id, item.name]));

  return (
    <Layout>
      <div className="space-y-6">
        <section>
          <h2 className="display text-xl">课程内容</h2>
          <p className="faint mt-1 text-xs">
            先修关系整批提交：成环时整批拒绝，并返回环路；被版本引用的知识点只能停用。
          </p>
        </section>

        <section className="sheet sheet-pad">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="display text-sm">课程信息</h3>
            <span className="faint text-xs">
              {course ? "当前状态：" + (course.status === "enabled" ? "启用" : "已停用") : ""}
            </span>
          </div>
          <div className="mt-2 grid gap-4 sm:grid-cols-3">
            <div className="field-row">
              <label htmlFor="course-name">名称</label>
              <input
                id="course-name"
                className="input"
                placeholder={course?.name ?? ""}
                value={courseName}
                onChange={(event) => setCourseName(event.target.value)}
              />
            </div>
            <div className="field-row">
              <label htmlFor="course-hours">总学时</label>
              <input
                id="course-hours"
                className="input num"
                placeholder={course ? String(course.total_hours) : ""}
                value={courseHours}
                onChange={(event) => setCourseHours(event.target.value)}
                inputMode="numeric"
              />
            </div>
            <div className="flex items-end gap-2">
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
                className="btn btn-quiet"
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
        </section>

        <ErrorBox error={patchCourse.error ?? disableCourse.error} />

        <section className="sheet sheet-pad">
          <h3 className="display text-sm">新增知识点</h3>
          <div className="mt-2 grid gap-4 sm:grid-cols-2">
            <div className="field-row">
              <label htmlFor="cname">名称</label>
              <input id="cname" className="input" value={name}
                     onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="field-row">
              <label htmlFor="cchapter">章节</label>
              <input id="cchapter" className="input" value={chapter}
                     onChange={(event) => setChapter(event.target.value)} />
            </div>
            <div className="field-row">
              <label htmlFor="cdiff">难度</label>
              <input id="cdiff" type="number" min={1} max={5} className="input num" value={difficulty}
                     onChange={(event) => setDifficulty(Number(event.target.value))} />
            </div>
            <div className="field-row">
              <label htmlFor="cmin">参考时长</label>
              <div className="flex items-baseline gap-2">
                <input id="cmin" type="number" min={5} max={600} className="input num"
                       value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} />
                <span className="faint text-xs">分钟</span>
              </div>
            </div>
          </div>
          <div className="mt-4">
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
        </section>

        <ErrorBox error={createConcept.error ?? submitPrereqs.error} />

        <section className="sheet sheet-pad">
          <h3 className="display text-sm">知识点（{list.length}）</h3>
          <table className="ledger mt-2">
            <thead>
              <tr>
                <th>ID</th>
                <th>名称</th>
                <th>章节</th>
                <th>难度</th>
                <th>时长</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {list.map((item) => (
                <tr key={item.concept_id}>
                  <td className="num">{item.concept_id}</td>
                  <td>{item.name}</td>
                  <td>{item.chapter}</td>
                  <td className="num">{item.difficulty}</td>
                  <td className="num">{item.reference_minutes}</td>
                  <td style={{ color: item.status === "enabled" ? "var(--moss)" : "var(--ink-3)" }}>
                    {item.status === "enabled" ? "启用" : "停用"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="sheet sheet-pad">
          <h3 className="display text-sm">先修关系（{edges.length}）</h3>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
            <select className="input" style={{ width: "11rem" }} value={fromId}
                    onChange={(event) => setFromId(event.target.value === "" ? "" : Number(event.target.value))}>
              <option value="">先修</option>
              {list.map((item) => (
                <option key={item.concept_id} value={item.concept_id}>{item.name}</option>
              ))}
            </select>
            <span className="faint">先于</span>
            <select className="input" style={{ width: "11rem" }} value={toId}
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

          <ul className="mt-3 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
            {edges.map((edge) => (
              <li key={edge.from_concept_id + "-" + edge.to_concept_id} className="muted">
                {byId.get(edge.from_concept_id) ?? edge.from_concept_id} 先于{" "}
                {byId.get(edge.to_concept_id) ?? edge.to_concept_id}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </Layout>
  );
}
