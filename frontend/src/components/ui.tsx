import { cloneElement, isValidElement, useId } from "react";
import type { ReactElement, ReactNode } from "react";

/* ---------------- 图标：内联 SVG，避免引入图标库 ---------------- */
type IconName =
  | "board" | "draft" | "adjust" | "history" | "version" | "sliders" | "book"
  | "check" | "clock" | "alert" | "spark" | "logout" | "plus" | "close" | "chevron";

const PATHS: Record<IconName, ReactNode> = {
  board: (
    <>
      <rect x="3" y="4" width="18" height="17" rx="3" />
      <path d="M8 2v4M16 2v4M3 10h18" />
    </>
  ),
  draft: (
    <>
      <path d="M14 3v5h5" />
      <path d="M19 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h9l6 6v11a1 1 0 0 1-1 1Z" />
      <path d="M9 13h6M9 17h4" />
    </>
  ),
  adjust: (
    <>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2.2" />
      <circle cx="10" cy="17" r="2.2" />
    </>
  ),
  history: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </>
  ),
  version: (
    <>
      <circle cx="6" cy="6" r="2.6" />
      <circle cx="6" cy="18" r="2.6" />
      <circle cx="18" cy="12" r="2.6" />
      <path d="M8.6 6H13a3 3 0 0 1 3 3v.4M8.6 18H13a3 3 0 0 0 3-3v-.4" />
    </>
  ),
  sliders: (
    <>
      <path d="M4 6h16M4 12h16M4 18h16" />
      <circle cx="9" cy="6" r="2" />
      <circle cx="15" cy="12" r="2" />
      <circle cx="8" cy="18" r="2" />
    </>
  ),
  book: (
    <>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5Z" />
      <path d="M4 20.5V5.5" />
    </>
  ),
  check: <path d="M4 12.5 9 17.5 20 6.5" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 1.8" />
    </>
  ),
  alert: (
    <>
      <path d="M12 3.5 21 19H3Z" />
      <path d="M12 9v4.5M12 16.5v.5" />
    </>
  ),
  spark: (
    <>
      <path d="M12 3v4M12 17v4M4.5 12h4M15.5 12h4M6.7 6.7l2.8 2.8M14.5 14.5l2.8 2.8M17.3 6.7l-2.8 2.8M9.5 14.5l-2.8 2.8" />
    </>
  ),
  logout: (
    <>
      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
      <path d="M10 8l-4 4 4 4M6 12h9" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  chevron: <path d="M9 6l6 6-6 6" />,
};

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="nav-icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

/* ---------------- 卡片 ---------------- */
export function Card({
  children, className = "", quiet = false,
}: {
  children: ReactNode; className?: string; quiet?: boolean;
}) {
  return <section className={"card" + (quiet ? " card-quiet" : "") + " " + className}>{children}</section>;
}

export function CardHead({
  title, hint, action,
}: {
  title: ReactNode; hint?: ReactNode; action?: ReactNode;
}) {
  return (
    <header className="card-head">
      <div>
        <h2 className="h2">{title}</h2>
        {hint ? <p className="sub" style={{ marginTop: 2 }}>{hint}</p> : null}
      </div>
      {action}
    </header>
  );
}

/* ---------------- 统计 ---------------- */
export function Stat({
  label, value, unit, ratio,
}: {
  label: ReactNode; value: ReactNode; unit?: string; ratio?: number;
}) {
  return (
    <div className="stat">
      <p className="stat-label">{label}</p>
      <p className="stat-value num">
        {value}
        {unit ? <small>{unit}</small> : null}
      </p>
      {ratio === undefined ? null : (
        <div className="stat-track">
          <span
            style={{
              transform: "scaleX(" + Math.min(1, Math.max(0, ratio)).toFixed(3) + ")",
            }}
          />
        </div>
      )}
    </div>
  );
}

export function Ring({ percent, caption }: { percent: number; caption: string }) {
  const value = Math.min(100, Math.max(0, Math.round(percent)));
  return (
    <div className="ring" style={{ ["--p" as string]: value }}>
      <div className="ring-inner">
        <div>
          <div className="ring-value num">{value}%</div>
          <div className="faint" style={{ fontSize: 10.5 }}>{caption}</div>
        </div>
      </div>
    </div>
  );
}

/* ---------------- 空状态 ---------------- */
export function EmptyState({
  title, hint, action,
}: {
  title: string; hint?: string; action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name="spark" size={18} />
      </span>
      <p className="h2" style={{ fontSize: 14 }}>{title}</p>
      {hint ? <p className="sub" style={{ maxWidth: 380 }}>{hint}</p> : null}
      {action}
    </div>
  );
}

/* ---------------- 分段控件 ---------------- */
export function Segmented<T extends string>({
  value, options, onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="seg" role="group" aria-label="视图切换">
      {options.map((item) => (
        <button
          key={item.value}
          type="button"
          aria-pressed={value === item.value}
          data-on={value === item.value}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- 字段 ---------------- */
export function Field({
  label, hint, children,
}: {
  label: string; hint?: string; children: ReactNode;
}) {
  const id = useId();
  const control =
    isValidElement(children) && typeof children.type === "string"
      ? cloneElement(children as ReactElement<{ id?: string }>, { id })
      : children;

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {control}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}

/** 只给读屏用的文本（表头、跳转提示等）。 */
export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="sr-only">{children}</span>;
}
