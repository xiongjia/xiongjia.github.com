import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "tauri-demo-theme";

/** `null` when nothing was stored or storage is unavailable. */
function readStoredTheme(): boolean | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === null ? null : stored === "dark";
  } catch {
    // Storage can throw in private modes; fall back to the OS preference.
    return null;
  }
}

function storeTheme(dark: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
  } catch {
    // Losing the preference is acceptable.
  }
}

function initialDark(): boolean {
  return readStoredTheme() ?? window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Toggles the shadcn `dark` class on <html> and remembers the choice. */
export function ThemeToggle() {
  const [dark, setDark] = useState(initialDark);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  function toggle() {
    const next = !dark;
    setDark(next);
    storeTheme(next);
  }

  return (
    <Button
      variant="outline"
      size="icon"
      aria-label="Toggle dark mode"
      data-testid="theme-toggle"
      onClick={toggle}
    >
      {dark ? <Sun /> : <Moon />}
    </Button>
  );
}
