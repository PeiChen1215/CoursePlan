import { useSearchParams } from "react-router-dom";
import { Layout } from "../components/Layout";
import { ErrorBox } from "../components/ErrorBox";
import { Card, CardHead, EmptyState, VisuallyHidden } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { useDiff, usePlans, useVersions } from "../hooks/queries";

export function VersionsPage() {
  const plans = usePlans();
  const plan = plans.data?.items?.[0] ?? null;
  const planId = plan?.plan_id ?? 0;
  const versions = useVersions(planId || null);
  const [params, setParams] = useSearchParams();
  const from = Number(params.get("from") ?? 0) || null;
  const to = Number(params.get("to") ?? 0) || null;

  function compare(versionNo: number) {
    const search = new URLSearchParams(params);
    search.set("from", String(versionNo));
    if (plan?.current_version) search.set("to", String(plan.current_version));
    setParams(search, { replace: true });
  }
  const diff = useDiff(planId, from, to);

  const items = versions.data?.items ?? [];
  const current = plan?.current_version ?? null;

  return (
    <Layout>
      <header className="page-head">
        <div>
          <h1 className="h1">版本</h1>
          <p className="sub">已确认的版本只读。差异按稳定任务 ID 比对，分新增、移除、移动、时长变化四类。</p>
        </div>
        {current ? <span className="chip" data-tone="brand">当前 v{current}</span> : null}
      </header>

      <div className="stack">
        {versions.error ? <ErrorBox error={versions.error} /> : null}

        {items.length === 0 ? (
          <EmptyState title="还没有确认过的版本" hint="在「草案」里生成并确认一次，就会产生 v1。" />
        ) : (
          <Card>
            <CardHead title="版本历史" />
            <div className="card-body" style={{ paddingTop: 0, paddingLeft: 8, paddingRight: 8 }}>
              <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>版本</th>
                    <th>原因</th>
                    <th>说明</th>
                    <th>任务</th>
                    <th>片</th>
                    <th>确认时间</th>
                    <th>
                      <VisuallyHidden>操作</VisuallyHidden>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.version_no} data-current={row.version_no === current}>
                      <td className="num">
                        v{row.version_no}
                        {row.version_no === current ? (
                          <span className="chip" data-tone="brand" style={{ marginLeft: 8 }}>当前</span>
                        ) : null}
                      </td>
                      <td>{row.change_reason}</td>
                      <td className="row-sub">{row.change_note}</td>
                      <td className="num">{row.tasks}</td>
                      <td className="num">{row.slices}</td>
                      <td className="row-sub num">{formatDateTime(row.created_at)}</td>
                      <td>
                        <button className="link-btn" onClick={() => compare(row.version_no)}>
                          与当前对比
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          </Card>
        )}

        {items.length <= 1 ? (
          <Card className="card-pad" quiet>
            <p className="h3">怎么产生第二个版本</p>
            <p className="sub" style={{ marginTop: 6 }}>
              去「调整」选一个原因（比如进度落后），重排后确认，就会生成 v2；
              这里可以按类别看到新增、移除、移动和时长变化。
            </p>
          </Card>
        ) : null}

        {diff.data ? (
          <Card>
            <CardHead title={"v" + from + " → v" + to} hint="按类别列出变化的任务" />
            <div className="card-body">
              <div className="grid-3" style={{ gap: 12 }}>
                {([
                  ["新增", diff.data.added, "done"],
                  ["移除", diff.data.removed, "danger"],
                  ["移动", diff.data.moved, "warn"],
                  ["时长变化", diff.data.resized, "brand"],
                ] as const).map(([label, ids, tone]) => (
                  <div key={label} className="card card-quiet card-pad" style={{ padding: "12px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span className="h3">{label}</span>
                      <span className="chip" data-tone={tone}>{ids.length}</span>
                    </div>
                    <p className="row-sub" style={{ marginTop: 6 }}>
                      {ids.length ? ids.join("、") : "无"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        ) : null}
      </div>
    </Layout>
  );
}
