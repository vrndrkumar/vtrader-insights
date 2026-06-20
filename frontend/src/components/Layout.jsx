import { Link, NavLink, Outlet } from "react-router-dom";
import { BarChart2, FileText, LayoutDashboard, Loader2, Sparkles, TrendingUp, Bell } from "lucide-react";
import SearchBar from "./SearchBar";
import ThemeToggle from "./ThemeToggle";
import { useJob } from "../lib/JobContext";

function AnalyzeAllBtn() {
  const { job, isRunning, startBatchJob } = useJob();
  const pct = job?.total ? Math.round(((job.completed + job.failed) / job.total) * 100) : 0;

  return (
    <button
      onClick={() => startBatchJob(null)}
      disabled={isRunning}
      title="Run fresh analysis for all active stocks"
      className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all disabled:opacity-70 disabled:cursor-wait shrink-0 no-print"
      style={{ background: "linear-gradient(135deg,var(--gold),var(--gold-2))", color: "var(--bg)" }}
    >
      {isRunning
        ? <><Loader2 size={14} className="animate-spin" />Scanning {job.completed}/{job.total} ({pct}%)</>
        : <><Sparkles size={14} />Run Full Scan</>}
    </button>
  );
}

const navBase = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all";

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
      {/* Gold accent top line */}
      <div className="h-0.5 w-full gradient-gold" />

      <header
        className="sticky top-0 z-40 border-b no-print"
        style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-sm)" }}
      >
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 h-14 flex items-center gap-3">

          {/* Brand */}
          <Link to="/" className="flex items-center gap-2.5 shrink-0 group">
            <div className="h-8 w-8 rounded-lg gradient-gold flex items-center justify-center shadow-md">
              <TrendingUp size={16} style={{ color: "var(--bg)" }} strokeWidth={2.5} />
            </div>
            <div className="leading-none">
              <div className="font-display font-bold text-sm tracking-wide" style={{ color: "var(--text-1)" }}>
                VTrader
              </div>
              <div className="text-[9px] font-semibold tracking-[0.15em] uppercase" style={{ color: "var(--gold)" }}>
                Stock Intelligence
              </div>
            </div>
          </Link>

          <div className="w-px h-6 mx-1 hidden sm:block" style={{ background: "var(--line)" }} />

          <SearchBar className="flex-1 max-w-md" />

          <nav className="hidden md:flex items-center gap-0.5 ml-auto">
            <NavLink to="/" end className={({ isActive }) =>
              `${navBase} ${isActive ? "font-semibold" : ""}`}
              style={({ isActive }) => ({
                color: isActive ? "var(--gold)" : "var(--text-2)",
                background: isActive ? "var(--gold-dim)" : "transparent",
              })}
            >
              <LayoutDashboard size={15} />Dashboard
            </NavLink>
            <NavLink to="/report" className={({ isActive }) =>
              `${navBase} ${isActive ? "font-semibold" : ""}`}
              style={({ isActive }) => ({
                color: isActive ? "var(--gold)" : "var(--text-2)",
                background: isActive ? "var(--gold-dim)" : "transparent",
              })}
            >
              <FileText size={15} />Research Report
            </NavLink>
          </nav>

          <div className="flex items-center gap-2 ml-2">
            <ThemeToggle />
            <AnalyzeAllBtn />
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1440px] mx-auto px-4 sm:px-6 py-6 w-full">
        <Outlet />
      </main>

      <footer className="border-t no-print" style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
        <div className="max-w-[1440px] mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-3 text-xs" style={{ color: "var(--text-3)" }}>
          <div className="flex items-center gap-2">
            <span className="font-display font-semibold" style={{ color: "var(--gold)" }}>VTrader Stock Intelligence</span>
            <span>·</span>
            <span>insights.vtrader.in</span>
            <span>·</span>
            <span>Analysis is for informational purposes only. Not financial advice.</span>
          </div>
          <span className="font-mono" style={{ color: "var(--text-3)" }}>© 2026 VTrader</span>
        </div>
      </footer>
    </div>
  );
}