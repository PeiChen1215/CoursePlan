import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "../hooks/useTheme";
import { Layout } from "./Layout";

vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ me: { user_id: 42, username: "alice", role: "student" }, logout: vi.fn() }) }));
vi.mock("../hooks/queries", () => ({ usePlans: () => ({ data: { items: [{ current_version: 1, course_name: "软件工程" }] } }) }));

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("studypath.welcome.v1.42", "done");
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});

function AppLayout() { return <ThemeProvider><MemoryRouter><Layout><p>课程内容</p></Layout></MemoryRouter></ThemeProvider>; }

describe("Layout", () => {
  it("collapses the sidebar while preserving accessible navigation", async () => {
    render(<AppLayout />);
    await userEvent.click(screen.getByRole("button", { name: "收起侧栏" }));
    expect(localStorage.getItem("studypath.sidebar-collapsed")).toBe("true");
    expect(screen.getByRole("button", { name: "展开侧栏" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("link", { name: "学习看板" })).toBeInTheDocument();
  });

  it("shows onboarding only for a first visit and allows reopening it", async () => {
    localStorage.removeItem("studypath.welcome.v1.42");
    render(<AppLayout />);
    expect(screen.getByRole("dialog", { name: "欢迎来到学径" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "稍后设置" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem("studypath.welcome.v1.42")).toBe("done");
    await userEvent.click(screen.getAllByRole("button", { name: "开始指南" })[0]);
    expect(screen.getByRole("dialog", { name: "欢迎来到学径" })).toBeInTheDocument();
  });
});
