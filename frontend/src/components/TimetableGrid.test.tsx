import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimetableGrid } from "./TimetableGrid";
import type { BoardTask } from "../hooks/queries";

describe("TimetableGrid", () => {
  it("counts only the displayed week's daily workload", () => {
    const task: BoardTask = {
      task_id: 1, concept_id: 1, concept_name: "需求获取", kind: "study",
      minutes: 60, start: "2026-11-09T19:00", end: "2026-11-09T20:00",
      done: false, overdue: false, issue_codes: [], slice_no: 1, slice_total: 1,
    };
    render(<TimetableGrid monday={new Date(2026, 10, 9)} onSelect={vi.fn()}
      tasks={[task, { ...task, task_id: 2, start: "2026-11-16T19:00", end: "2026-11-16T20:00" }]} />);
    expect(screen.getByText("60 分")).toBeInTheDocument();
    expect(screen.queryByText("120 分")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});
