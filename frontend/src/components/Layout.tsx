import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { usePlans } from "../hooks/queries";
import { Icon } from "./ui";
import { AppearanceMenu } from "./AppearanceMenu";
import { Onboarding } from "./Onboarding";
import { readPreference, savePreference } from "../lib/preferences";

const LEARN = [
  { to: "/board", label: "学习看板", icon: "board" as const },
  { to: "/draft", label: "计划草案", icon: "draft" as const },
  { to: "/adjust", label: "计划调整", icon: "adjust" as const },
  { to: "/timeline", label: "学习记录", icon: "history" as const },
  { to: "/versions", label: "版本历史", icon: "version" as const },
];

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth();
  const guideKey = "studypath.welcome.v1." + (me?.user_id ?? "guest");
  const [guideOpen, setGuideOpen] = useState(() => readPreference(guideKey) !== "done");
  const [collapsed, setCollapsed] = useState(() => {
    const saved = readPreference("studypath.sidebar-collapsed");
    return saved == null ? (window.matchMedia?.("(max-width: 1050px)").matches ?? false) : saved === "true";
  });
  function toggleSidebar() {
    const next = !collapsed;
    setCollapsed(next);
    savePreference("studypath.sidebar-collapsed", String(next));
  }
  function dismissGuide() { savePreference(guideKey, "done"); setGuideOpen(false); }
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => { window.scrollTo({ top: 0 }); }, [location.pathname]);
  const current = LEARN.find((item) => item.to === location.pathname)?.label
    ?? (location.pathname === "/admin" ? "课程内容" : "学习偏好");
  const plans = usePlans();
  const plan = plans.data?.items?.[0];

  return (
    <div className="app-shell" data-collapsed={collapsed}>
      <a className="skip-link" href="#main">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <div className="sidebar-head"><div className="brand">
          <span className="brand-mark"><Icon name="path" size={30} /></span>
          <div>
            <div className="brand-name">学径</div>
            <div className="brand-sub">STUDYPATH</div>
          </div>
        </div><button className="btn btn-quiet btn-icon sidebar-toggle" onClick={toggleSidebar} aria-label={collapsed ? "展开侧栏" : "收起侧栏"} title={collapsed ? "展开侧栏" : "收起侧栏"} aria-expanded={!collapsed}><Icon name={collapsed ? "expand" : "collapse"} size={20} /></button></div>

        <nav className="nav-group" aria-label="学习导航">
          <span className="nav-label">学习</span>
          {LEARN.map((item) => (
            <NavLink key={item.to} to={item.to} className="nav-item" title={item.label} aria-label={item.label}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <nav className="nav-group" aria-label="设置导航">
          <span className="nav-label">设置</span>
          <NavLink to="/constraint" className="nav-item" title="学习偏好" aria-label="学习偏好">
            <Icon name="sliders" />
            <span>学习偏好</span>
          </NavLink>
          {me?.role === "admin" ? (
            <NavLink to="/admin" className="nav-item" title="课程内容" aria-label="课程内容">
              <Icon name="book" />
              <span>课程内容</span>
            </NavLink>
          ) : null}
        </nav>

        <Link className="btn sidebar-create" to="/constraint" title="制定计划" aria-label="制定计划"><Icon name="plus" /><span>制定计划</span></Link>

        <div className="sidebar-foot">
          <button className="guide-trigger" title="开始指南" aria-label="开始指南" onClick={() => setGuideOpen(true)}><Icon name="help" size={20} /><span>开始指南</span></button>
          <AppearanceMenu />
          {plan ? (
            <p className="faint" style={{ fontSize: 11, padding: "0 6px 8px" }}>
              {plan.course_name}
              <span style={{ display: "block" }}>当前 v{plan.current_version ?? "—"}</span>
            </p>
          ) : null}
          <div className="user-card">
            <span className="avatar">{(me?.username ?? "?").slice(0, 1).toUpperCase()}</span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <p className="row-title" style={{ fontSize: 12.5 }}>{me?.username}</p>
              <p className="row-sub">{me?.role === "admin" ? "课程管理员" : "学生"}</p>
            </div>
            <button
              className="btn btn-quiet btn-sm"
              title="退出"
              aria-label="退出"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <Icon name="logout" size={15} />
            </button>
          </div>
        </div>
      </aside>

      <div className="workspace">
        <div className="mobile-topbar">
          <span className="mobile-brand"><Icon name="path" size={24} />{current}</span>
          <div className="mobile-tools">
            <button className="btn btn-quiet btn-icon" title="开始指南" aria-label="开始指南" onClick={() => setGuideOpen(true)}><Icon name="help" /></button>
            <AppearanceMenu />
            {me?.role === "admin" ? <Link className="btn btn-quiet btn-icon" title="课程内容" aria-label="课程内容" to="/admin"><Icon name="book" /></Link> : null}
            <Link className="btn btn-quiet btn-icon" title="学习偏好" aria-label="学习偏好" to="/constraint"><Icon name="sliders" /></Link>
            <button className="btn btn-quiet btn-icon" title="退出" aria-label="退出" onClick={() => { logout(); navigate("/login"); }}><Icon name="logout" /></button>
          </div>
        </div>
        <main className="main" id="main">{children}</main>
      </div>
      {guideOpen ? <Onboarding onDismiss={dismissGuide} hasConfirmedPlan={Boolean(plan?.current_version)} isAdmin={me?.role === "admin"} /> : null}
    </div>
  );
}
