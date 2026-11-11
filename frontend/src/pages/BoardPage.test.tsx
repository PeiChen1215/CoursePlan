import type { ReactNode } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BoardPage } from "./BoardPage";
import { BOARD_VIEW_KEY } from "../lib/preferences";

const { mutate, state } = vi.hoisted(() => ({ mutate: vi.fn(), state: { readonly: false } }));
vi.mock("../components/Layout", () => ({ Layout: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ push: vi.fn() }) }));
vi.mock("../hooks/queries", () => ({
  usePlans: () => ({ data: { items: [{ plan_id: 1, current_version: 1, course_name: "软件工程" }] }, isPending: false }),
  useConstraint: () => ({ data: { deadline: "2026-12-05" } }),
  useSubmitEvent: () => ({ mutate, isPending: false }),
  useBoard: () => {
    const now = new Date();
    const day = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
    return { isPending: false, data: {
      readonly: state.readonly, unscheduled: [], issues: [],
      progress: { completion_rate: 0, done_tasks: 0, total_tasks: 1, planned_minutes: 60, actual_minutes: 0 },
      tasks: [{ task_id: 1, concept_id: 1, concept_name: "需求获取", start: day + "T19:00", end: day + "T20:00", minutes: 60, kind: "study", done: false, overdue: false, issue_codes: [], slice_no: 1, slice_total: 1 }],
    } };
  },
}));

beforeEach(() => { localStorage.clear(); state.readonly = false; mutate.mockClear(); });

describe("BoardPage", () => {
  it("shows today's actionable tasks and submits a completion", async () => {
    render(<MemoryRouter><BoardPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /1\s*项待办/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "完成打卡" }));
    expect(mutate).toHaveBeenCalledWith({ taskId: 1, type: "done", minutes: 60 }, expect.any(Object));
  });

  it("keeps readonly plans from being completed", () => {
    state.readonly = true;
    render(<MemoryRouter><BoardPage /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "完成打卡" })).toBeDisabled();
  });

  it("remembers the selected board and respects an explicit URL view", async () => {
    localStorage.setItem(BOARD_VIEW_KEY, "all");
    render(<MemoryRouter initialEntries={["/board?view=today"]}><BoardPage /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "今天" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "全部任务" }));
    expect(localStorage.getItem(BOARD_VIEW_KEY)).toBe("all");
    expect(screen.getByRole("heading", { name: /1\s*个学习时段/ })).toBeInTheDocument();
  });

  it("restores the user's preferred board when the URL has no override", () => {
    localStorage.setItem(BOARD_VIEW_KEY, "week");
    render(<MemoryRouter><BoardPage /></MemoryRouter>);
    expect(within(screen.getByRole("group", { name: "视图切换" })).getByRole("button", { name: "本周" })).toHaveAttribute("aria-pressed", "true");
  });
});
