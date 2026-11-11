import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import { BOARD_VIEW_KEY, readBoardView, savePreference } from "../lib/preferences";
import { Icon } from "./ui";

const THEMES = [
  { value: "light", label: "白色", icon: "sun" },
  { value: "dark", label: "黑色", icon: "moon" },
  { value: "system", label: "跟随系统", icon: "monitor" },
] as const;
const VIEWS = [
  { value: "today", label: "今日任务", icon: "check" },
  { value: "week", label: "周课表", icon: "board" },
  { value: "all", label: "全部安排", icon: "draft" },
] as const;
const TITLES = ["欢迎来到学径", "选择你的学习看板", "准备好了，开始吧"];

export function Onboarding({ onDismiss, hasConfirmedPlan, isAdmin = false }: { onDismiss: () => void; hasConfirmedPlan: boolean; isAdmin?: boolean }) {
  const { mode, setMode } = useTheme();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [view, setView] = useState(readBoardView);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => { dialog?.close(); previous?.focus({ preventScroll: true }); };
  }, []);

  useEffect(() => { headingRef.current?.focus({ preventScroll: true }); }, [step]);

  function start(path?: string) {
    savePreference(BOARD_VIEW_KEY, view);
    onDismiss();
    navigate(path ?? (isAdmin ? "/admin" : hasConfirmedPlan ? "/board?view=" + view : "/constraint"));
  }

  return <dialog className="onboarding" ref={dialogRef} aria-labelledby="welcome-title" onCancel={(event) => { event.preventDefault(); onDismiss(); }}>
    <div className="welcome-top"><span className="welcome-brand"><Icon name="path" size={24} />学径</span><button className="btn btn-quiet btn-icon" aria-label="关闭新手引导" onClick={onDismiss}><Icon name="close" /></button></div>
    <div className="welcome-progress" aria-label={"引导步骤 " + (step + 1) + " / 3"}>{[0, 1, 2].map((value) => <span key={value} data-active={value <= step} />)}</div>
    <div className="welcome-content" key={step}>
      <p className="welcome-step">{String(step + 1).padStart(2, "0")} / 03</p>
      <h2 id="welcome-title" ref={headingRef} tabIndex={-1}>{TITLES[step]}</h2>
      {step === 0 ? <fieldset className="welcome-options"><legend>外观</legend>{THEMES.map((theme) => <label key={theme.value} data-selected={mode === theme.value}>
        <input type="radio" name="welcome-theme" value={theme.value} checked={mode === theme.value} onChange={() => setMode(theme.value)} />
        <Icon name={theme.icon} size={22} /><span>{theme.label}</span><Icon name={mode === theme.value ? "check" : "circle"} size={17} />
      </label>)}</fieldset> : null}
      {step === 1 ? <fieldset className="welcome-options"><legend>默认看板</legend>{VIEWS.map((item) => <label key={item.value} data-selected={view === item.value}>
        <input type="radio" name="welcome-view" value={item.value} checked={view === item.value} onChange={() => setView(item.value)} />
        <Icon name={item.icon} size={22} /><span>{item.label}</span><Icon name={view === item.value ? "check" : "circle"} size={17} />
      </label>)}</fieldset> : null}
      {step === 2 ? <ol className="welcome-journey">
        {[
          { title: isAdmin ? "维护课程与知识点" : "设定目标与时间", to: isAdmin ? "/admin" : "/constraint", icon: "sliders" as const },
          { title: isAdmin ? "设置学习偏好" : "确认学习计划", to: isAdmin ? "/constraint" : "/draft", icon: "draft" as const },
          { title: "查看今日任务", to: "/board?view=" + view, icon: "check" as const },
        ].map((item, index) => <li key={item.to}><button onClick={() => start(item.to)}><span className="journey-number">{index + 1}</span><Icon name={item.icon} size={20} /><span>{item.title}</span><Icon name="chevron" /></button></li>)}
      </ol> : null}
    </div>
    <footer className="welcome-actions"><button className="btn btn-quiet" onClick={step ? () => setStep(step - 1) : onDismiss}>{step ? "上一步" : "稍后设置"}</button>
      <button className="btn" onClick={step < 2 ? () => setStep(step + 1) : () => start()}>{step < 2 ? "继续" : isAdmin ? "管理课程" : hasConfirmedPlan ? "开始学习" : "制定第一份计划"}<Icon name="chevron" /></button>
    </footer>
  </dialog>;
}
