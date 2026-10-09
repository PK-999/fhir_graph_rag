import Link from "next/link";
import { Activity, Users, GitGraph, Filter, ShieldCheck, Database, Bot } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

export function Sidebar() {
  return (
    <div className="flex h-screen w-64 flex-col bg-background/50 backdrop-blur-xl text-foreground relative shadow-[1px_0_15px_-5px_rgba(0,0,0,0.05)] dark:shadow-[1px_0_15px_-5px_rgba(0,0,0,0.5)] z-20">
      <div className="flex h-16 items-center px-6 mt-2">
        <h1 className="text-xl font-bold flex items-center gap-2 text-foreground tracking-tight">
          <div className="p-1.5 bg-blue-500/10 rounded-lg">
            <Database className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
          FHIRGraph
        </h1>
      </div>
      <nav className="flex-1 space-y-1.5 p-4 overflow-y-auto">
        <Link href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-all duration-300 hover:translate-x-1">
          <Activity className="h-4 w-4" />
          Dashboard
        </Link>
        <Link href="/patients" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-all duration-300 hover:translate-x-1">
          <Users className="h-4 w-4" />
          Patients
        </Link>
        <Link href="/graph" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-all duration-300 hover:translate-x-1">
          <GitGraph className="h-4 w-4" />
          Graph Explorer
        </Link>
        <Link href="/cohorts" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-all duration-300 hover:translate-x-1">
          <Filter className="h-4 w-4" />
          Cohorts
        </Link>
        <Link href="/data-quality" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-all duration-300 hover:translate-x-1">
          <ShieldCheck className="h-4 w-4" />
          Data Quality
        </Link>
        <Link href="/lineage" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-all duration-300 hover:translate-x-1">
          <Database className="h-4 w-4" />
          Lineage
        </Link>
        <div className="pt-4 pb-1">
          <p className="text-xs font-semibold text-muted-foreground/60 uppercase tracking-wider px-3">Intelligence</p>
        </div>
        <Link href="/assistant" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-300 text-blue-600 dark:text-blue-400 hover:bg-blue-500/10 hover:translate-x-1">
          <Bot className="h-4 w-4" />
          AI Assistant
        </Link>
      </nav>
      <div className="p-4 space-y-4">
        <ThemeToggle />
        <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 text-xs shadow-sm backdrop-blur-sm">
          <p className="font-semibold text-amber-700 dark:text-amber-500 mb-1">⚠️ Demo Environment</p>
          <p className="text-amber-600/80 dark:text-amber-500/80">Synthetic data only. Do not upload PHI.</p>
        </div>
      </div>
    </div>
  );
}
