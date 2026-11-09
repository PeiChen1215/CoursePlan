import { STATUS_STYLES, pickStatus } from "../lib/format";
import type { TaskStatus } from "../lib/format";

interface Props {
  done: boolean;
  overdue: boolean;
  conflict: boolean;
  extra?: string;
}

/** 文字 + 符号 + 描边颜色三通道，颜色永远不是唯一线索。 */
export function StatusBadge({ done, overdue, conflict, extra }: Props) {
  const status: TaskStatus = pickStatus({ done, overdue, conflict });
  const style = STATUS_STYLES[status];
  return (
    <span className="badge-soft" data-status={status}>
      <span aria-hidden>{style.icon}</span>
      {style.label}
      {extra ? <span style={{ opacity: 0.7 }}>· {extra}</span> : null}
    </span>
  );
}
