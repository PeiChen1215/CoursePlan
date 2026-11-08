import type { IssueRow } from "../hooks/queries";

const LABEL: Record<string, string> = { ERROR: "错误", WARN: "警告", INFO: "提示" };

export function IssueList({ issues }: { issues: IssueRow[] }) {
  if (!issues.length) {
    return <p className="muted text-sm">校验通过，没有问题项。</p>;
  }
  return (
    <ul>
      {issues.map((issue, index) => (
        <li key={issue.code + index} className="issue" data-level={issue.level}>
          <span className="issue-code">{issue.code}</span>
          <span>
            {issue.message}
            <span className="faint">（{LABEL[issue.level] ?? issue.level}）</span>
            {issue.suggestion ? (
              <span className="block muted text-xs">建议：{issue.suggestion}</span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}
