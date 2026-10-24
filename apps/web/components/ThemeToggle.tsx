"use client";
import { useEffect, useState } from "react";

type Choice = "system" | "light" | "dark";
const KEY = "bionexus-theme";

function apply(choice: Choice) {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

/** Light by default; dark or follow-the-device are opt-in. The choice is a per-browser convenience only. */
export default function ThemeToggle() {
  const [choice, setChoice] = useState<Choice>("light");
  useEffect(() => {
    try { setChoice((localStorage.getItem(KEY) as Choice) || "system"); } catch { /* storage may be blocked */ }
  }, []);
  const pick = (next: Choice) => {
    setChoice(next); apply(next);
    try { localStorage.setItem(KEY, next); } catch { /* ignore */ }
  };
  return (
    <div className="themebar" role="group" aria-label="Colour theme">
      {(["light", "dark", "system"] as Choice[]).map((c) => (
        <button key={c} type="button" aria-pressed={choice === c} onClick={() => pick(c)}>{c[0].toUpperCase() + c.slice(1)}</button>
      ))}
    </div>
  );
}
