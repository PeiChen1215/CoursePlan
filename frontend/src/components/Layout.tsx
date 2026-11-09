import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { usePlans } from "../hooks/queries";
import { Icon } from "./ui";

const LEARN = [
  { to: "/board", label: "看板", icon: "board" as const },
  { to: "/draft", label: "草案", icon: "draft" as const },
  { to: "/adjust", label: "调整", icon: "adjust" as const },
  { to: "/timeline", label: "记录", icon: "history" as const },
  { to: "/versions", label: "版本", icon: "version" as const },
];

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const plans = usePlans();
  const plan = plans.data?.items?.[0];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">径</span>
          <div>
            <div className="brand-name">学径</div>
            <div className="brand-sub">STUDYPATH</div>
          </div>
        </div>

        <nav className="nav-group">
          <span className="nav-label">学习</span>
          {LEARN.map((item) => (
            <NavLink key={item.to} to={item.to} className="nav-item">
              <Icon name={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <nav className="nav-group">
          <span className="nav-label">设置</span>
          <NavLink to="/constraint" className="nav-item">
            <Icon name="sliders" />
            填写约束
          </NavLink>
          {me?.role === "admin" ? (
            <NavLink to="/admin" className="nav-item">
              <Icon name="book" />
              课程内容
            </NavLink>
          ) : null}
        </nav>

        <div className="sidebar-foot">
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

      <main className="main">{children}</main>
    </div>
  );
}
