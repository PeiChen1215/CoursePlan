import { useEffect, useId, useRef, useState } from "react";
import { useTheme } from "../hooks/useTheme";
import { Icon } from "./ui";

const OPTIONS = [
  { value: "light", label: "白色", icon: "sun" },
  { value: "dark", label: "黑色", icon: "moon" },
  { value: "system", label: "跟随系统", icon: "monitor" },
] as const;

export function AppearanceMenu() {
  const { mode, resolved, setMode } = useTheme();
  const ref = useRef<HTMLDetailsElement>(null);
  const name = useId();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function close(event: PointerEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) ref.current.open = false;
    }
    function escape(event: KeyboardEvent) {
      if (event.key !== "Escape" || !ref.current) return;
      ref.current.open = false;
      ref.current.querySelector("summary")?.focus();
    }
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return <details ref={ref} className="appearance-menu" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary title="外观设置" aria-label="外观设置"><Icon name={resolved === "dark" ? "moon" : "sun"} size={22} /><span>外观</span></summary>
    <fieldset className="appearance-options">
      <legend>外观</legend>
      {OPTIONS.map((option) => <label key={option.value} data-selected={mode === option.value}>
        <input type="radio" name={name} value={option.value} checked={mode === option.value}
          onChange={() => {
            setMode(option.value);
            if (ref.current) {
              ref.current.open = false;
              ref.current.querySelector("summary")?.focus({ preventScroll: true });
            }
          }} />
        <Icon name={option.icon} size={18} /><span>{option.label}</span>
        {mode === option.value ? <Icon name="check" size={16} /> : null}
      </label>)}
    </fieldset>
  </details>;
}
