import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

const { login } = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ login }) }));

describe("LoginPage", () => {
  it("toggles password visibility without submitting", async () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    const password = screen.getByLabelText("密码");
    expect(password).toHaveAttribute("type", "password");
    await userEvent.click(screen.getByRole("button", { name: "显示密码" }));
    expect(password).toHaveAttribute("type", "text");
    await userEvent.click(screen.getByRole("button", { name: "隐藏密码" }));
    expect(password).toHaveAttribute("type", "password");
    expect(login).not.toHaveBeenCalled();
  });

  it("keeps login errors visible and allows retry", async () => {
    login.mockRejectedValueOnce(new Error("账号或密码错误"));
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByText(/账号或密码错误/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登录" })).toBeEnabled();
  });
});
