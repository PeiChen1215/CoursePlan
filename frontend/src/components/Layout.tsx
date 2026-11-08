import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { usePlans } from "../hooks/queries";

const NAV = [
  { to: "/board", label: "课表" },
  { to: "/constraint", label: "填写约束" },
  { to: "/draft", label: "草案" },
  { to: "/adjust", label: "调整" },
  { to: "/timeline", label: "记录" },
  { to: "/versions", label: "版本" },
];

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const plans = usePlans();
  const plan = plans.data?.items?.[0];

  return (
    <div className="relative z-10 mx-auto max-w-6xl px-5">
      <header className="nameplate">
        <h1>学径</h1>
        <span className="faint text-xs">
          {plan
            ? plan.course_name + (plan.current_version ? " · 第 " + plan.current_version + " 版" : " · 未确认")
            : "把一门课，排成一条走得完的路"}
        </span>
        <span className="ml-auto flex items-baseline gap-3 text-xs">
          <span className="muted">
            {me?.username}（{me?.role === "admin" ? "课程管理员" : "学生"}）
          </span>
          <button
            className="btn-link text-xs"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            退出
          </button>
        </span>
      </header>

      <nav className="tabs">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} className="tab">
            {item.label}
          </NavLink>
        ))}
        {me?.role === "admin" ? (
          <NavLink to="/admin" className="tab">
            课程内容
          </NavLink>
        ) : null}
      </nav>

      <main className="pb-16">{children}</main>
    </div>
  );
}
