import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink } from "lucide-react";
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { api, useJobEvents } from "../api";
import { useToast } from "../components/toast";
import { Card, ErrorBox, Stepper, StatusBadge, Timeline } from "../components/ui";

export default function Push() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const toast = useToast();
  const { data: job } = useQuery({ queryKey: ["job", id], queryFn: () => api.job(id) });
  const { events, error, done } = useJobEvents(id, "push");
  useEffect(() => { if (done) qc.invalidateQueries({ queryKey: ["job", id] }); }, [done, id, qc]);

  const status = job?.status;
  useEffect(() => {
    if (status === "COMPLETED") toast("Repository published");
    if (status === "FAILED") toast("Push failed", "error");
  }, [status, toast]);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center gap-3"><h1 className="text-xl font-semibold">{job?.repo_name ?? "Push"}</h1>{job && <StatusBadge status={job.status} />}</div>
      <Stepper current={job?.status === "COMPLETED" ? 4 : 3} />
      <Card title="Progress"><Timeline events={events} running={!done} /></Card>
      {error && <ErrorBox>{error}</ErrorBox>}
      {job?.status === "FAILED" && <ErrorBox>{job.error}</ErrorBox>}
      {job?.status === "COMPLETED" && job.github_url && (
        <Card>
          <p className="flex items-center gap-2 font-medium"><CheckCircle2 size={18} className="text-ok" />Repository successfully published</p>
          <a className="mt-3 inline-flex items-center gap-2 text-sm text-accent underline" href={job.github_url} target="_blank" rel="noreferrer">Open on GitHub <ExternalLink size={14} /></a>
        </Card>
      )}
    </div>
  );
}
