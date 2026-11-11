import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "../hooks/useTheme";
import { BOARD_VIEW_KEY } from "../lib/preferences";
import { Onboarding } from "./Onboarding";

beforeEach(() => {
  localStorage.clear();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});

function Location() { const location = useLocation(); return <output>{location.pathname + location.search}</output>; }

describe("Onboarding", () => {
  it("applies appearance and view preferences before starting the real board", async () => {
    const dismiss = vi.fn();
    render(<ThemeProvider><MemoryRouter><Onboarding hasConfirmedPlan onDismiss={dismiss} /><Location /></MemoryRouter></ThemeProvider>);
    expect(screen.getByRole("dialog")).toHaveAccessibleName("欢迎来到学径");
    await userEvent.click(screen.getByLabelText("黑色"));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    await userEvent.click(screen.getByRole("button", { name: "继续" }));
    await userEvent.click(screen.getByLabelText("全部安排"));
    await userEvent.click(screen.getByRole("button", { name: "继续" }));
    await userEvent.click(screen.getByRole("button", { name: "开始学习" }));
    expect(localStorage.getItem(BOARD_VIEW_KEY)).toBe("all");
    expect(screen.getByRole("status")).toHaveTextContent("/board?view=all");
    expect(dismiss).toHaveBeenCalledOnce();
  });

  it("lets users skip without making navigation mandatory", async () => {
    const dismiss = vi.fn();
    render(<ThemeProvider><MemoryRouter><Onboarding hasConfirmedPlan={false} onDismiss={dismiss} /></MemoryRouter></ThemeProvider>);
    await userEvent.click(screen.getByRole("button", { name: "稍后设置" }));
    expect(dismiss).toHaveBeenCalledOnce();
    expect(localStorage.getItem(BOARD_VIEW_KEY)).toBeNull();
  });

  it("takes course administrators to course management", async () => {
    render(<ThemeProvider><MemoryRouter><Onboarding hasConfirmedPlan={false} isAdmin onDismiss={vi.fn()} /><Location /></MemoryRouter></ThemeProvider>);
    await userEvent.click(screen.getByRole("button", { name: "继续" }));
    await userEvent.click(screen.getByRole("button", { name: "继续" }));
    await userEvent.click(screen.getByRole("button", { name: "管理课程" }));
    expect(screen.getByRole("status")).toHaveTextContent("/admin");
  });
});
