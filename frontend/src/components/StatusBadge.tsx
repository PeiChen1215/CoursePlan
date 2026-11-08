import { STATUS_STYLES, pickStatus } from "../lib/format";
import type { TaskStatus } from "../lib/format";

interface Props {
  done: boolean;
  overdue: boolean;
  conflict: boolean;
  extra?: string;
}

/** 文字 + 底色双通道，黑白打印也能读（D06 §11.6.2）。 */
export function StatusBadge({ done, overdue, conflict, extra }: Props) {
  const status: TaskStatus = pickStatus({ done, overdue, conflict });
  const style = STATUS_STYLES[status];
  return (
    <span
      data-status={status}
      className={"inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs " + style.text + " " + style.bg}
    >
      <span aria-hidden>{style.icon}</span>
      {style.label}
      {extra ? <span className="font-normal opacity-80">· {extra}</span> : null}
    </span>
  );
}
