import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { usePlans } from "../hooks/queries";

const NAV = [
  { to: "/board", label: "看板" },
  { to: "/constraint", label: "约束" },
  { to: "/draft", label: "草案" },
  { to: "/versions", label: "版本" },
];

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const plans = usePlans();
  const plan = plans.data?.items?.[0];

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <div>
            <h1 className="text-base font-semibold text-slate-900">学径 StudyPath</h1>
            <p className="text-xs text-slate-500">
              {plan
                ? plan.course_name + " · " + (plan.current_version ? "v" + plan.current_version : "未确认")
                : "课程学习规划辅助系统"}
            </p>
          </div>
          <nav className="flex flex-1 items-center gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  "rounded px-2.5 py-1 text-sm " +
                  (isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100")
                }
              >
                {item.label}
              </NavLink>
            ))}
            {me?.role === "admin" ? (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  "rounded px-2.5 py-1 text-sm " +
                  (isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100")
                }
              >
                课程管理
              </NavLink>
            ) : null}
          </nav>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>
              {me?.username}（{me?.role === "admin" ? "管理员" : "学生"}）
            </span>
            <button
              className="btn-ghost"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              退出
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
