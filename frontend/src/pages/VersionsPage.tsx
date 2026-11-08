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
  const current = plan?.current_version ?? null;

  return (
    <Layout>
      <div className="space-y-6">
        <section>
          <h2 className="display text-xl">版本</h2>
          <p className="faint mt-1 text-xs">
            已确认的版本只读。差异按稳定任务 ID 比对，分新增、移除、移动、时长变化四类。
          </p>
        </section>

        {versions.error ? <ErrorBox error={versions.error} /> : null}

        <section className="sheet sheet-pad">
          <table className="ledger">
            <thead>
              <tr>
                <th>版本</th>
                <th>原因</th>
                <th>任务</th>
                <th>片</th>
                <th>确认时间</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.version_no} data-current={row.version_no === current}>
                  <td className="num">
                    v{row.version_no}
                    {row.version_no === current ? <span className="faint text-xs">（当前）</span> : null}
                  </td>
                  <td>{row.change_reason}</td>
                  <td className="num">{row.tasks}</td>
                  <td className="num">{row.slices}</td>
                  <td className="num faint text-xs">{row.created_at}</td>
                  <td>
                    <button className="btn-link text-xs"
                            onClick={() => {
                              setFrom(row.version_no);
                              setTo(current);
                            }}>
                      与当前对比
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="faint py-4 text-center text-sm">
                    还没有确认过的版本。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>

        {diff.data ? (
          <section className="sheet sheet-pad">
            <h3 className="display text-sm">
              v{from} → v{to}
            </h3>
            <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <DiffCell label="新增" ids={diff.data.added} tone="var(--moss)" />
              <DiffCell label="移除" ids={diff.data.removed} tone="var(--crimson)" />
              <DiffCell label="移动" ids={diff.data.moved} tone="var(--rust)" />
              <DiffCell label="时长变化" ids={diff.data.resized} tone="var(--ink-2)" />
            </div>
          </section>
        ) : null}
      </div>
    </Layout>
  );
}

function DiffCell({ label, ids, tone }: { label: string; ids: number[]; tone: string }) {
  return (
    <div>
      <p className="text-xs" style={{ color: tone }}>
        {label} <span className="num">{ids.length}</span>
      </p>
      <p className="faint mt-1 text-xs">{ids.length ? ids.join("、") : "无"}</p>
    </div>
  );
}
