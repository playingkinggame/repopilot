import { AlertTriangle, Check, Loader2, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { JobEvent } from "../api";

export const inputCls =
  "w-full rounded border border-line bg-bg px-3 py-2 text-sm text-fg placeholder:text-mute focus:outline-none focus:ring-1 focus:ring-accent";

export function Button({ variant = "primary", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  const v = { primary: "bg-accent text-bg font-medium hover:opacity-90", ghost: "border border-line text-fg hover:bg-panel", danger: "border border-line text-bad hover:bg-panel" }[variant];
  return <button {...p} className={`inline-flex items-center gap-2 rounded px-3 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${v} ${className}`} />;
}

export function Card({ title, action, children }: { title?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded border border-line bg-panel p-4">
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return <div role="alert" className="flex items-start gap-2 rounded border border-bad/60 p-3 text-sm text-bad"><X size={16} className="mt-0.5 shrink-0" />{children}</div>;
}

export function WarnBox({ children }: { children: ReactNode }) {
  return <div className="flex items-start gap-2 rounded border border-warn/60 p-3 text-sm text-warn"><AlertTriangle size={16} className="mt-0.5 shrink-0" /><div>{children}</div></div>;
}

const STEPS = ["Scan", "Plan", "Review", "Push"];
export function Stepper({ current }: { current: number }) {
  return (
    <ol className="mb-6 flex items-center gap-2 text-sm">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs ${i < current ? "border-accent bg-accent text-bg" : i === current ? "border-accent text-accent" : "border-line text-mute"}`}>
            {i < current ? <Check size={12} /> : i + 1}
          </span>
          <span className={i <= current ? "text-fg" : "text-mute"}>{s}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-8 bg-line" />}
        </li>
      ))}
    </ol>
  );
}

const BADGES: Record<string, [string, string]> = {
  CREATED: ["Created", "text-mute"], SCANNING: ["Scanning", "text-warn"], PLANNING: ["Planning", "text-warn"], REVIEW: ["In review", "text-accent"],
  APPROVED: ["Approved", "text-accent"], PUSHING: ["Pushing", "text-warn"], COMPLETED: ["Completed", "text-ok"], FAILED: ["Failed", "text-bad"], BLOCKED: ["Blocked", "text-bad"],
};
export function StatusBadge({ status }: { status: string }) {
  const [label, cls] = BADGES[status] ?? [status, "text-mute"];
  return <span className={`rounded border border-line px-2 py-0.5 text-xs ${cls}`}>{label}</span>;
}

export function Timeline({ events, running }: { events: JobEvent[]; running: boolean }) {
  return (
    <ul className="space-y-2 font-mono text-sm" aria-live="polite">
      {events.filter((e) => e.type === "log" || e.type === "failed").map((e, i, arr) => {
        const active = running && i === arr.length - 1 && e.type === "log";
        return (
          <li key={i} className={`flex items-start gap-2 ${e.type === "failed" ? "text-bad" : active ? "text-fg" : "text-mute"}`}>
            {e.type === "failed" ? <X size={14} className="mt-1" /> : active ? <Loader2 size={14} className="mt-1 animate-spin" /> : <Check size={14} className="mt-1 text-ok" />}
            <span>{e.message}</span>
          </li>
        );
      })}
    </ul>
  );
}
