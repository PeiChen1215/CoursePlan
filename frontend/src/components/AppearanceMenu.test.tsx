import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppearanceMenu } from "./AppearanceMenu";
import { ThemeProvider, THEME_KEY } from "../hooks/useTheme";

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("AppearanceMenu", () => {
  it("switches to black and remembers the selection", async () => {
    render(<ThemeProvider><AppearanceMenu /></ThemeProvider>);
    await userEvent.click(screen.getByLabelText("外观设置"));
    await userEvent.click(screen.getByLabelText("黑色"));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(screen.getByLabelText("外观设置").parentElement).not.toHaveAttribute("open");
  });

  it("restores a saved preference and can return to white", async () => {
    localStorage.setItem(THEME_KEY, "dark");
    render(<ThemeProvider><AppearanceMenu /></ThemeProvider>);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    await userEvent.click(screen.getByLabelText("外观设置"));
    await userEvent.click(screen.getByLabelText("白色"));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
  });

  it("follows the operating system when no explicit preference is saved", () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    render(<ThemeProvider><AppearanceMenu /></ThemeProvider>);
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
  });
});
