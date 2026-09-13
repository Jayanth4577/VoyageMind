"use client";

import { useState } from "react";

/** Light/dark toggle. Persists to localStorage; defaults to system preference. */
export default function ThemeToggle({ className = "" }: { className?: string }) {
  // Lazy init reads the live class; suppressHydrationWarning covers the SSR icon.
  const [dark, setDark] = useState<boolean | null>(() =>
    typeof document === "undefined"
      ? null
      : document.documentElement.classList.contains("dark"),
  );

  function toggle() {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("vm-theme", next ? "dark" : "light");
    setDark(next);
  }

  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme" : "Dark theme"}
      suppressHydrationWarning
      className={`inline-flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface text-ink transition hover:bg-surface2 ${className}`}
    >
      <span suppressHydrationWarning className="text-sm">
        {dark === null ? "🌗" : dark ? "☀️" : "🌙"}
      </span>
    </button>
  );
}
