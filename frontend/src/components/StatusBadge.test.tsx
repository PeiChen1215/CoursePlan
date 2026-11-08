import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("未开始时显示“未开始”", () => {
    render(<StatusBadge done={false} overdue={false} conflict={false} />);
    expect(screen.getByText("未开始")).toBeInTheDocument();
  });

  it("冲突优先显示，并带问题码", () => {
    render(<StatusBadge done overdue conflict extra="TIME_OVERLAP" />);
    expect(screen.getByText("冲突")).toBeInTheDocument();
    expect(screen.getByText(/TIME_OVERLAP/)).toBeInTheDocument();
  });

  it("逾期文案可读（不是只有颜色）", () => {
    render(<StatusBadge done={false} overdue conflict={false} />);
    expect(screen.getByText("逾期")).toBeInTheDocument();
  });
});
