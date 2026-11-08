import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useToast } from "../components/Toast";
import {
  useConcepts, useCreateConcept, usePrereqs, useSubmitPrereqs,
} from "../hooks/queries";

export function AdminPage() {
  const toast = useToast();
  const courseId = 1;
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

  return (
    <Layout>
      <div className="space-y-4">
        <section>
          <h2 className="text-lg font-semibold">课程内容管理</h2>
          <p className="text-xs text-slate-500">
            先修关系整批提交；成环时整批拒绝并返回环路。
          </p>
        </section>

        <section className="card grid gap-3 sm:grid-cols-5">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="cname">名称</label>
            <input id="cname" className="input" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="cchapter">章节</label>
            <input id="cchapter" className="input" value={chapter} onChange={(event) => setChapter(event.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="cdiff">难度</label>
            <input id="cdiff" type="number" min={1} max={5} className="input" value={difficulty}
                   onChange={(event) => setDifficulty(Number(event.target.value))} />
          </div>
          <div>
            <label className="label" htmlFor="cmin">参考时长</label>
            <input id="cmin" type="number" min={5} max={600} className="input" value={minutes}
                   onChange={(event) => setMinutes(Number(event.target.value))} />
          </div>
          <div className="sm:col-span-5">
            <button
              className="btn-primary"
              disabled={!name || createConcept.isPending}
              onClick={() =>
                createConcept.mutate(
                  { name, chapter, difficulty, reference_minutes: minutes },
                  {
                    onSuccess: () => {
                      toast.push("已新增知识点", "success");
                      setName("");
                    },
                    onError: (error) =>
                      toast.push(error instanceof Error ? error.message : "新增失败", "error"),
                  },
                )
              }
            >
              新增知识点
            </button>
          </div>
        </section>

        <ErrorBox error={createConcept.error ?? submitPrereqs.error} />

        <section className="card">
          <h3 className="text-sm font-semibold text-slate-700">知识点（{list.length}）</h3>
          <table className="mt-2 w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="py-1">ID</th>
                <th>名称</th>
                <th>章节</th>
                <th>难度</th>
                <th>时长</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {list.map((item) => (
                <tr key={item.concept_id} className="border-t border-slate-100">
                  <td className="py-1">{item.concept_id}</td>
                  <td>{item.name}</td>
                  <td>{item.chapter}</td>
                  <td>{item.difficulty}</td>
                  <td>{item.reference_minutes}</td>
                  <td className={item.status === "enabled" ? "text-emerald-700" : "text-slate-400"}>
                    {item.status === "enabled" ? "启用" : "停用"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="card space-y-2">
          <h3 className="text-sm font-semibold text-slate-700">先修关系（{edges.length}）</h3>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <select className="input w-40" value={fromId}
                    onChange={(event) => setFromId(event.target.value === "" ? "" : Number(event.target.value))}>
              <option value="">先修知识点</option>
              {list.map((item) => (
                <option key={item.concept_id} value={item.concept_id}>{item.name}</option>
              ))}
            </select>
            <span>→</span>
            <select className="input w-40" value={toId}
                    onChange={(event) => setToId(event.target.value === "" ? "" : Number(event.target.value))}>
              <option value="">后继知识点</option>
              {list.map((item) => (
                <option key={item.concept_id} value={item.concept_id}>{item.name}</option>
              ))}
            </select>
            <button
              className="btn-primary"
              disabled={fromId === "" || toId === "" || submitPrereqs.isPending}
              onClick={() =>
                submitPrereqs.mutate([[Number(fromId), Number(toId)]], {
                  onSuccess: (data) => toast.push("已保存 " + data.saved + " 条", "success"),
                  onError: (error) =>
                    toast.push(error instanceof Error ? error.message : "提交失败", "error"),
                })
              }
            >
              提交
            </button>
          </div>
          <ul className="text-xs text-slate-500">
            {edges.map((edge) => (
              <li key={edge.from_concept_id + "-" + edge.to_concept_id}>
                {edge.from_concept_id} → {edge.to_concept_id}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </Layout>
  );
}
