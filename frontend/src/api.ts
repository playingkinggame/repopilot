import { useEffect, useState } from "react";

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Commit { message: string; files: string[]; reason: string }
export interface Plan {
  repo_name: string; description: string; topics: string[]; visibility: "public" | "private"; commits: Commit[];
  readme: string; gitignore: string; license: "MIT" | "none"; warnings: string[]; branch: string;
}
export interface Finding { severity: string; file: string; line: number; type: string; message: string }
export interface Job {
  id: string; folder: string; repo_name: string; description: string; visibility: string; status: string; commits: number;
  created_at: string; completed_at: string | null; github_url: string | null; error: string | null; mode: "new" | "update";
}
export interface JobDetail extends Job {
  plan: Plan | null; security: { blocked: { path: string; reason: string }[]; findings: Finding[] }; available_files: string[];
  sync: { owner: string; name: string; branch: string; ahead: number; changes: { path: string; status: string }[] } | null;
}
export interface Inspect { is_repo: boolean; reason?: string; owner?: string; name?: string; branch?: string; ahead?: number; changed?: number }
export interface Settings { groq_model: string; max_agent_tool_calls: number; max_file_size_mb: number; groq_configured: boolean; github_configured: boolean }
export interface JobEvent { phase: string; type: "log" | "plan_ready" | "completed" | "failed"; message: string }
export interface NewJob { folder: string; repo_name: string; description: string; visibility: string; mode: "new" | "update" }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new Error(`Cannot reach the RepoPilot backend at ${API_URL}. Is it running?`);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = (await res.json()).detail;
      msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { msg: string }) => x.msg).join("; ") : msg;
    } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  createJob: (b: NewJob) => post<Job>("/api/jobs", b),
  scan: (id: string) => post<JobDetail>(`/api/jobs/${id}/scan`),
  plan: (id: string) => post<Job>(`/api/jobs/${id}/plan`),
  job: (id: string) => request<JobDetail>(`/api/jobs/${id}`),
  jobs: () => request<Job[]>("/api/jobs"),
  savePlan: (id: string, plan: Plan) => request<JobDetail>(`/api/jobs/${id}/plan`, { method: "PUT", body: JSON.stringify(plan) }),
  approve: (id: string, acknowledge_warnings: boolean) => post<Job>(`/api/jobs/${id}/approve`, { acknowledge_warnings }),
  push: (id: string) => post<Job>(`/api/jobs/${id}/push`),
  inspect: (folder: string) => request<Inspect>(`/api/inspect?folder=${encodeURIComponent(folder)}`),
  settings: () => request<Settings>("/api/settings"),
};

export function useJobEvents(jobId: string | null, phase: "plan" | "push") {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!jobId) return;
    setEvents([]);
    setError(null);
    const es = new EventSource(`${API_URL}/api/jobs/${jobId}/events?phase=${phase}`);
    es.onmessage = (m) => {
      const e: JobEvent = JSON.parse(m.data);
      setEvents((p) => [...p, e]);
      if (e.type !== "log") es.close();
    };
    es.onerror = () => { if (es.readyState === EventSource.CLOSED) setError("Lost the connection to the backend."); };
    return () => es.close();
  }, [jobId, phase]);
  const last = events[events.length - 1];
  return { events, error, done: !!last && last.type !== "log" };
}
