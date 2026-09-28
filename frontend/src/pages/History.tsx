import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, StatusBadge } from "../components/ui";

export default function History() {
  const { data, error, isLoading } = useQuery({ queryKey: ["jobs"], queryFn: api.jobs });
  if (error) return <ErrorBox>{(error as Error).message}</ErrorBox>;
  if (isLoading) return <p className="text-sm text-mute">Loading history…</p>;
  if (!data?.length) return <p className="text-sm text-mute">No pushes yet. <Link className="text-accent underline" to="/">Start a new push</Link>.</p>;
  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-4 text-xl font-semibold">History</h1>
      <div className="overflow-x-auto rounded border border-line bg-panel">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line text-mute"><tr>{["Repository", "Status", "Commits", "Created", "GitHub"].map((h) => <th key={h} className="px-4 py-2 font-medium">{h}</th>)}</tr></thead>
          <tbody>
            {data.map((j) => (
              <tr key={j.id} className="border-b border-line last:border-0">
                <td className="px-4 py-2"><Link className="hover:text-accent" to={j.status === "REVIEW" ? `/jobs/${j.id}/review` : `/jobs/${j.id}/push`}>{j.repo_name}</Link><div className="truncate font-mono text-xs text-mute">{j.folder}</div></td>
                <td className="px-4 py-2"><StatusBadge status={j.status} />{j.error && <div className="mt-1 max-w-xs truncate text-xs text-bad" title={j.error}>{j.error}</div>}</td>
                <td className="px-4 py-2">{j.commits}</td>
                <td className="px-4 py-2 text-mute">{new Date(j.created_at).toLocaleString()}</td>
                <td className="px-4 py-2">{j.github_url ? <a className="inline-flex items-center gap-1 text-accent" href={j.github_url} target="_blank" rel="noreferrer">Open <ExternalLink size={12} /></a> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
