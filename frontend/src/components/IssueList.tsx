import type { IssueRow } from "../hooks/queries";

const LABEL: Record<string, string> = { ERROR: "错误", WARN: "警告", INFO: "提示" };

// 校验码 → 中文短标签；保留原始码在 title 里便于排查
const CODE_LABEL: Record<string, string> = {
  SLOT_INVALID: "时间片无效",
  CAP_EXCEEDED: "容量不足",
  TIME_OVERLAP: "时间重叠",
  PREREQ_VIOLATED: "先修倒置",
  DEADLINE_UNREACHABLE: "超出截止",
  CAP_TIGHT: "容量偏紧",
  ISOLATED_CONCEPT: "孤立知识点",
  COURSE_BUDGET_EXCEEDED: "超出课程学时",
};

export function IssueList({ issues }: { issues: IssueRow[] }) {
  if (!issues.length) {
    return <p className="sub">校验通过，没有问题项。</p>;
  }
  return (
    <div>
      {issues.map((issue, index) => (
        <div key={issue.code + index} className="issue-row" data-level={issue.level}>
          <span className="issue-code" title={issue.code}>
            {CODE_LABEL[issue.code] ?? issue.code}
          </span>
          <span>
            {issue.message}
            <span className="faint">（{LABEL[issue.level] ?? issue.level}）</span>
            {issue.suggestion ? (
              <span style={{ display: "block" }} className="row-sub">
                建议：{issue.suggestion}
              </span>
            ) : null}
          </span>
        </div>
      ))}
    </div>
  );
}
