import { useState } from "react";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { useDiff, usePlans, useVersions } from "../hooks/queries";

export function VersionsPage() {
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const planId = plan?.plan_id ?? 0;
  const versions = useVersions(planId || null);
  const [from, setFrom] = useState<number | null>(null);
  const [to, setTo] = useState<number | null>(null);
  const diff = useDiff(planId, from, to);

  const items = versions.data?.items ?? [];

  return (
    <Layout>
      <div className="space-y-4">
        <section>
          <h2 className="text-lg font-semibold">版本历史</h2>
          <p className="text-xs text-slate-500">已确认的版本只读；差异按任务 ID 对比四类变化。</p>
        </section>

        {versions.error ? <ErrorBox error={versions.error} /> : null}

        <section className="card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="py-1">版本</th>
                <th>原因</th>
                <th>任务</th>
                <th>时间片</th>
                <th>创建时间</th>
                <th>对比</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.version_no} className="border-t border-slate-100">
                  <td className="py-1">v{row.version_no}</td>
                  <td>{row.change_reason}</td>
                  <td>{row.tasks}</td>
                  <td>{row.slices}</td>
                  <td className="text-xs text-slate-500">{row.created_at}</td>
                  <td>
                    <button className="btn-ghost" onClick={() => { setFrom(row.version_no); setTo(plan?.current_version ?? null); }}>
                      与当前对比
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-3 text-center text-sm text-slate-500">
                    还没有已确认的版本。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>

        {diff.data ? (
          <section className="card">
            <h3 className="text-sm font-semibold text-slate-700">
              v{from} → v{to} 的差异
            </h3>
            <div className="mt-2 grid gap-3 sm:grid-cols-4 text-sm">
              <DiffBlock title="新增" tone="text-emerald-700" ids={diff.data.added} />
              <DiffBlock title="移除" tone="text-rose-700" ids={diff.data.removed} />
              <DiffBlock title="移动" tone="text-amber-700" ids={diff.data.moved} />
              <DiffBlock title="时长变化" tone="text-slate-700" ids={diff.data.resized} />
            </div>
          </section>
        ) : null}
      </div>
    </Layout>
  );
}

function DiffBlock({ title, tone, ids }: { title: string; tone: string; ids: number[] }) {
  return (
    <div>
      <p className={"text-xs font-medium " + tone}>{title}（{ids.length}）</p>
      <p className="mt-1 text-xs text-slate-500">{ids.length ? ids.join("、") : "无"}</p>
    </div>
  );
}
