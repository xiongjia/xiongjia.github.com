import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { ThemeToggle } from "@/components/theme-toggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("flips the dark class on <html> and remembers the choice", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(false);

    await user.click(screen.getByTestId("theme-toggle"));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("tauri-demo-theme")).toBe("dark");

    await user.click(screen.getByTestId("theme-toggle"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("tauri-demo-theme")).toBe("light");
  });

  it("starts from the stored preference", () => {
    localStorage.setItem("tauri-demo-theme", "dark");
    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("does not write the storage key before the user chooses", () => {
    render(<ThemeToggle />);

    expect(localStorage.getItem("tauri-demo-theme")).toBeNull();
  });
});
