import { Loader2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, useJobEvents } from "../api";
import { useToast } from "../components/toast";
import { Button, Card, ErrorBox, inputCls, Stepper, Timeline } from "../components/ui";

export default function NewPush() {
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState({ folder: "", repo_name: "", description: "", visibility: "private" });
  const [jobId, setJobId] = useState<string | null>(null);
  const [stage, setStage] = useState<"idle" | "scan" | "plan">("idle");
  const [err, setErr] = useState<string | null>(null);
  const { events, error } = useJobEvents(stage === "plan" ? jobId : null, "plan");

  useEffect(() => {
    const last = events[events.length - 1];
    if (!last) return;
    if (last.type === "plan_ready" && jobId) nav(`/jobs/${jobId}/review`);
    if (last.type === "failed") { setErr(last.message); toast(last.message, "error"); setStage("idle"); }
  }, [events, jobId, nav, toast]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!f.folder.trim()) return setErr("Enter the path of your local project folder.");
    if (!/^[A-Za-z0-9._-]{1,100}$/.test(f.repo_name)) return setErr("Repository name may only contain letters, numbers, '.', '-' and '_'.");
    try {
      setStage("scan");
      const job = await api.createJob(f);
      setJobId(job.id);
      await api.scan(job.id);
      await api.plan(job.id);
      setStage("plan");
    } catch (x) {
      setErr((x as Error).message);
      toast((x as Error).message, "error");
      setStage("idle");
    }
  }

  const busy = stage !== "idle";
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold">New push</h1>
      <p className="mb-5 text-sm text-mute">Point RepoPilot at a local project. Nothing is pushed until you approve the plan.</p>
      <Stepper current={stage === "plan" ? 1 : 0} />
      <form onSubmit={submit} className="space-y-4">
        <Card>
          <div className="space-y-4">
            <label className="block text-sm">Local folder path
              <input className={`${inputCls} mt-1 font-mono`} placeholder="C:\Users\you\Projects\my-project" value={f.folder} onChange={set("folder")} disabled={busy} />
            </label>
            <label className="block text-sm">Repository name
              <input className={`${inputCls} mt-1`} placeholder="my-project" value={f.repo_name} onChange={set("repo_name")} disabled={busy} />
            </label>
            <label className="block text-sm">Description
              <input className={`${inputCls} mt-1`} maxLength={350} value={f.description} onChange={set("description")} disabled={busy} />
            </label>
            <label className="block text-sm">Visibility
              <select className={`${inputCls} mt-1`} value={f.visibility} onChange={set("visibility")} disabled={busy}>
                <option value="private">Private</option>
                <option value="public">Public</option>
              </select>
            </label>
          </div>
        </Card>
        {err && <ErrorBox>{err}</ErrorBox>}
        {error && <ErrorBox>{error}</ErrorBox>}
        <Button type="submit" disabled={busy}>{busy && <Loader2 size={14} className="animate-spin" />}{busy ? "Working" : "Generate plan"}</Button>
      </form>
      {stage !== "idle" && (
        <div className="mt-6"><Card title="Progress"><Timeline events={events} running /></Card></div>
      )}
    </div>
  );
}
