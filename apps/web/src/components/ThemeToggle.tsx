"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <button className="flex items-center gap-2 p-2 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors opacity-50">
        <Sun className="h-[1.2rem] w-[1.2rem]" />
      </button>
    );
  }

  return (
    <button
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
      className="flex items-center gap-2 p-2 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors w-full"
      title="Toggle theme"
    >
      {theme === "light" ? (
        <>
          <Moon className="h-4 w-4 text-zinc-500" />
          <span className="text-sm font-medium text-zinc-600">Dark Mode</span>
        </>
      ) : (
        <>
          <Sun className="h-4 w-4 text-zinc-400" />
          <span className="text-sm font-medium text-zinc-300">Light Mode</span>
        </>
      )}
    </button>
  );
}
