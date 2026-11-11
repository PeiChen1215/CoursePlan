import { cloneElement, isValidElement, useId } from "react";
import type { ReactElement, ReactNode } from "react";
import { CalendarDays, FileText, SlidersHorizontal, History, GitBranch, Settings2,
  BookOpen, Check, Clock, TriangleAlert, Sparkles, LogOut, Plus, X, ChevronRight, Eye, EyeOff } from "lucide-react";

const ICONS = {
  board: CalendarDays, draft: FileText, adjust: SlidersHorizontal, history: History,
  version: GitBranch, sliders: Settings2, book: BookOpen, check: Check, clock: Clock,
  alert: TriangleAlert, spark: Sparkles, logout: LogOut, plus: Plus, close: X,
  chevron: ChevronRight, eye: Eye, eyeOff: EyeOff,
};

export function Icon({ name, size = 16 }: { name: keyof typeof ICONS; size?: number }) {
  const Glyph = ICONS[name];
  return <Glyph className="nav-icon" size={size} strokeWidth={1.7} aria-hidden="true" />;
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
