import { useQuery } from "@tanstack/react-query";
import { API_URL, api } from "../api";
import { Card, ErrorBox } from "../components/ui";

export default function SettingsPage() {
  const { data, error, isLoading } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  if (error) return <ErrorBox>{(error as Error).message}</ErrorBox>;
  if (isLoading || !data) return <p className="text-sm text-mute">Loading settings…</p>;
  const rows: [string, string][] = [
    ["Groq model", data.groq_model], ["Maximum agent tool calls", String(data.max_agent_tool_calls)],
    ["Maximum file size", `${data.max_file_size_mb} MB`], ["Frontend API URL", API_URL],
    ["Groq API key", data.groq_configured ? "Configured ••••••••••" : "Not configured"],
    ["GitHub token", data.github_configured ? "Configured ••••••••••" : "Not configured"],
  ];
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-xl font-semibold">Settings</h1>
      <Card><dl className="divide-y divide-line text-sm">{rows.map(([k, v]) => <div key={k} className="flex justify-between py-2"><dt className="text-mute">{k}</dt><dd className="font-mono">{v}</dd></div>)}</dl></Card>
      <p className="mt-3 text-xs text-mute">Change these values in the backend .env file and restart the backend.</p>
    </div>
  );
}
