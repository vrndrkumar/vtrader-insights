import { useEffect, useState } from "react";
import { Moon, Sun, Monitor } from "lucide-react";
import { getStoredTheme, setStoredTheme, applyTheme } from "../lib/theme";

const OPTIONS = [
  { key: "light",  icon: Sun,     label: "Light" },
  { key: "dark",   icon: Moon,    label: "Dark" },
  { key: "system", icon: Monitor, label: "System" },
];

export default function ThemeToggle() {
  const [theme, setTheme] = useState(getStoredTheme);
  const [open, setOpen]   = useState(false);

  const pick = (t) => {
    setTheme(t);
    setStoredTheme(t);
    applyTheme(t);
    setOpen(false);
  };

  const current = OPTIONS.find(o => o.key === theme) || OPTIONS[1];
  const Icon    = current.icon;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-all hover:border-[var(--gold)] hover:text-[var(--gold)]"
        style={{ borderColor: "var(--line)", color: "var(--text-2)", background: "var(--surface-2)" }}
        title="Switch theme"
      >
        <Icon size={14} />
        <span className="hidden sm:inline">{current.label}</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className="absolute right-0 mt-2 w-36 rounded-xl border shadow-lg z-50 overflow-hidden"
            style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-md)" }}
          >
            {OPTIONS.map(({ key, icon: I, label }) => (
              <button
                key={key}
                onClick={() => pick(key)}
                className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-left transition-colors"
                style={{
                  color: theme === key ? "var(--gold)" : "var(--text-2)",
                  background: theme === key ? "var(--gold-dim)" : "transparent",
                }}
                onMouseEnter={e => { if (theme !== key) e.currentTarget.style.background = "var(--surface-2)"; }}
                onMouseLeave={e => { if (theme !== key) e.currentTarget.style.background = "transparent"; }}
              >
                <I size={14} />
                {label}
                {theme === key && <span className="ml-auto text-[10px]">✓</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}