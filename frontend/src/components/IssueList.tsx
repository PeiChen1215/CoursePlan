import type { IssueRow } from "../hooks/queries";
import { summarizeIssues } from "../lib/format";

const LEVEL_STYLE: Record<string, string> = {
  ERROR: "border-rose-300 bg-rose-50 text-rose-800",
  WARN: "border-amber-300 bg-amber-50 text-amber-800",
  INFO: "border-slate-300 bg-slate-50 text-slate-700",
};

export function IssueList({ issues }: { issues: IssueRow[] }) {
  if (!issues.length) {
    return <p className="text-sm text-emerald-700">校验通过，没有问题项。</p>;
  }
  const summary = summarizeIssues(issues);
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">
        共 {issues.length} 项：错误 {summary.errors} · 警告 {summary.warns} · 提示 {summary.infos}
      </p>
      <ul className="space-y-1.5">
        {issues.map((issue, index) => (
          <li
            key={issue.code + "-" + index}
            className={"rounded border px-2 py-1.5 text-sm " + (LEVEL_STYLE[issue.level] ?? "")}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">
                {issue.level} · {issue.code}
              </span>
              {issue.concept_id != null ? (
                <span className="text-xs opacity-70">知识点 {issue.concept_id}</span>
              ) : null}
            </div>
            <p className="mt-0.5">{issue.message}</p>
            {issue.suggestion ? (
              <p className="mt-0.5 text-xs opacity-80">建议：{issue.suggestion}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
