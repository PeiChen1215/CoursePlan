import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskCard } from "./TaskCard";
import type { BoardTask } from "../hooks/queries";

const task: BoardTask = {
  task_id: 1,
  concept_id: 7,
  concept_name: "指针",
  kind: "study",
  minutes: 90,
  start: "2026-11-09T19:00",
  end: "2026-11-09T20:30",
  done: false,
  overdue: false,
  issue_codes: [],
};

describe("TaskCard", () => {
  it("未完成时显示“标记完成”", () => {
    render(<TaskCard task={task} readonly={false} onDone={vi.fn()} onCorrection={vi.fn()} onNote={vi.fn()} />);
    expect(screen.getByText("标记完成")).toBeInTheDocument();
    expect(screen.getByText("指针")).toBeInTheDocument();
  });

  it("只读时不显示任何打卡按钮", () => {
    render(<TaskCard task={task} readonly onDone={vi.fn()} onCorrection={vi.fn()} onNote={vi.fn()} />);
    expect(screen.queryByText("标记完成")).toBeNull();
    expect(screen.getByText("历史版本，只读")).toBeInTheDocument();
  });

  it("点击完成时把分钟数传出去", async () => {
    const onDone = vi.fn();
    render(<TaskCard task={task} readonly={false} onDone={onDone} onCorrection={vi.fn()} onNote={vi.fn()} />);
    await userEvent.clear(screen.getByLabelText("实际用时（分钟）"));
    await userEvent.type(screen.getByLabelText("实际用时（分钟）"), "75");
    await userEvent.click(screen.getByText("标记完成"));
    expect(onDone).toHaveBeenCalledWith(1, 75);
  });

  it("已完成时显示更正入口", () => {
    render(<TaskCard task={{ ...task, done: true }} readonly={false} onDone={vi.fn()} onCorrection={vi.fn()} onNote={vi.fn()} />);
    expect(screen.getByText("更正用时")).toBeInTheDocument();
    expect(screen.getByText(/重复打卡会被拒绝/)).toBeInTheDocument();
  });

  it("可以写备注", async () => {
    const onNote = vi.fn();
    render(<TaskCard task={task} readonly={false} onDone={vi.fn()} onCorrection={vi.fn()} onNote={onNote} />);
    await userEvent.click(screen.getByText("加备注"));
    await userEvent.type(screen.getByLabelText("备注"), "卡在指针偏移");
    await userEvent.click(screen.getByText("保存备注"));
    expect(onNote).toHaveBeenCalledWith(1, "卡在指针偏移");
  });
});
