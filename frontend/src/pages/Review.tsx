import { useQuery } from "@tanstack/react-query";
import { GitCommit, Plus, ShieldAlert, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, Commit, Plan } from "../api";
import { useToast } from "../components/toast";
import { Button, Card, ErrorBox, inputCls, Stepper, WarnBox } from "../components/ui";

export default function Review() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { data: job, error, isLoading } = useQuery({ queryKey: ["job", id], queryFn: () => api.job(id) });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [preview, setPreview] = useState(false);

  useEffect(() => { if (job?.plan && !plan) setPlan(job.plan); }, [job, plan]);

  if (error) return <ErrorBox>{(error as Error).message}</ErrorBox>;
  if (isLoading || !job) return <p className="text-sm text-mute">Loading plan…</p>;
  if (job.status !== "REVIEW" || !plan) {
    return <Card title="Nothing to review"><p className="text-sm text-mute">This job is {job.status.toLowerCase()}. <Link className="text-accent underline" to={`/jobs/${id}/push`}>View progress</Link></p></Card>;
  }

  const blocked = job.security.blocked;
  const assigned = new Set(plan.commits.flatMap((c) => c.files));
  const unassigned = job.available_files.filter((f) => !assigned.has(f));
  const setCommit = (i: number, patch: Partial<Commit>) => setPlan({ ...plan, commits: plan.commits.map((c, j) => (j === i ? { ...c, ...patch } : c)) });
  const move = (from: number, file: string, to: number) =>
    setPlan({ ...plan, commits: plan.commits.map((c, j) => (j === from ? { ...c, files: c.files.filter((x) => x !== file) } : j === to ? { ...c, files: [...c.files, file] } : c)) });

  async function approve() {
    if (!plan) return;
    setBusy(true);
    setErr(null);
    try {
      await api.savePlan(id, plan);
      await api.approve(id, ack);
      await api.push(id);
      nav(`/jobs/${id}/push`);
    } catch (x) {
      setErr((x as Error).message);
      toast((x as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-xl font-semibold">Review plan</h1>
      <Stepper current={2} />
      {blocked.length > 0 && (
        <WarnBox>
          <p className="font-medium">Security warning</p>
          <p>{blocked.length} sensitive file(s) were detected and are blocked from the push:</p>
          <ul className="mt-1 font-mono text-xs">{blocked.map((b) => <li key={b.path}>{b.path} <span className="text-mute">({b.reason})</span></li>)}</ul>
        </WarnBox>
      )}
      {plan.warnings.filter((w) => !w.includes("sensitive")).map((w) => <WarnBox key={w}>{w}</WarnBox>)}
      <Card title="Repository">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Name<input className={`${inputCls} mt-1`} value={plan.repo_name} onChange={(e) => setPlan({ ...plan, repo_name: e.target.value })} /></label>
          <label className="text-sm">Visibility
            <select className={`${inputCls} mt-1`} value={plan.visibility} onChange={(e) => setPlan({ ...plan, visibility: e.target.value as Plan["visibility"] })}>
              <option value="private">Private</option><option value="public">Public</option>
            </select>
          </label>
          <label className="text-sm sm:col-span-2">Description<input className={`${inputCls} mt-1`} maxLength={350} value={plan.description} onChange={(e) => setPlan({ ...plan, description: e.target.value })} /></label>
          <label className="text-sm sm:col-span-2">Topics (comma separated)
            <input className={`${inputCls} mt-1`} defaultValue={plan.topics.join(", ")} onBlur={(e) => setPlan({ ...plan, topics: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) })} />
          </label>
        </div>
      </Card>
      <Card title={`Commits (${plan.commits.length})`} action={<Button variant="ghost" onClick={() => setPlan({ ...plan, commits: [...plan.commits, { message: "chore: new commit", files: [], reason: "" }] })}><Plus size={14} />Add commit</Button>}>
        <div className="ml-2 space-y-4 border-l border-line pl-5">
          {plan.commits.map((c, i) => (
            <div key={i} className="relative rounded border border-line bg-bg p-3">
              <GitCommit size={16} className="absolute -left-[30px] top-3 rounded-full bg-panel text-accent" />
              <div className="flex gap-2">
                <input aria-label="Commit message" className={`${inputCls} font-mono`} value={c.message} onChange={(e) => setCommit(i, { message: e.target.value })} />
                <Button variant="danger" aria-label="Delete commit" onClick={() => setPlan({ ...plan, commits: plan.commits.filter((_, j) => j !== i) })}><Trash2 size={14} /></Button>
              </div>
              <input aria-label="Reason" className={`${inputCls} mt-2 text-mute`} placeholder="Why these files belong together" value={c.reason} onChange={(e) => setCommit(i, { reason: e.target.value })} />
              <ul className="mt-2 space-y-1 font-mono text-xs">
                {c.files.map((file) => (
                  <li key={file} className="flex items-center gap-2">
                    <span className="flex-1 truncate">{file}</span>
                    <select aria-label={`Move ${file}`} className="rounded border border-line bg-bg px-1 py-0.5" value="" onChange={(e) => e.target.value !== "" && move(i, file, Number(e.target.value))}>
                      <option value="">Move to…</option>
                      {plan.commits.map((o, j) => j !== i && <option key={j} value={j}>{o.message.slice(0, 40)}</option>)}
                    </select>
                    <button aria-label={`Remove ${file}`} className="text-mute hover:text-bad" onClick={() => setCommit(i, { files: c.files.filter((x) => x !== file) })}><X size={14} /></button>
                  </li>
                ))}
              </ul>
              {unassigned.length > 0 && (
                <select aria-label="Add file" className={`${inputCls} mt-2 font-mono text-xs`} value="" onChange={(e) => e.target.value && setCommit(i, { files: [...c.files, e.target.value] })}>
                  <option value="">Add a file…</option>
                  {unassigned.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              )}
            </div>
          ))}
        </div>
        {unassigned.length > 0 && <p className="mt-3 text-xs text-mute">{unassigned.length} file(s) are not in any commit and will not be pushed.</p>}
      </Card>
      <Card title="README.md" action={<Button variant="ghost" onClick={() => setPreview(!preview)}>{preview ? "Edit" : "Preview"}</Button>}>
        {preview ? <div className="md text-sm"><ReactMarkdown>{plan.readme}</ReactMarkdown></div>
          : <textarea aria-label="README" rows={12} className={`${inputCls} font-mono`} value={plan.readme} onChange={(e) => setPlan({ ...plan, readme: e.target.value })} />}
      </Card>
      <Card title=".gitignore"><textarea aria-label=".gitignore" rows={7} className={`${inputCls} font-mono`} value={plan.gitignore} onChange={(e) => setPlan({ ...plan, gitignore: e.target.value })} /></Card>
      <Card title="License">
        <select aria-label="License" className={inputCls} value={plan.license} onChange={(e) => setPlan({ ...plan, license: e.target.value as Plan["license"] })}>
          <option value="MIT">MIT</option><option value="none">No license</option>
        </select>
      </Card>
      {err && <ErrorBox>{err}</ErrorBox>}
      <div className="flex items-center gap-4">
        {blocked.length > 0 && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />I understand the blocked files will not be pushed</label>}
        <Button onClick={approve} disabled={busy || (blocked.length > 0 && !ack)}><ShieldAlert size={14} />{busy ? "Starting…" : "Approve & push"}</Button>
      </div>
    </div>
  );
}
