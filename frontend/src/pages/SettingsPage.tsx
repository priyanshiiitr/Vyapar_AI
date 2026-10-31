import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Card, CardTitle } from "@/components/ui/card";

export function SettingsPage() {
  const { data } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  return (
    <div className="space-y-4 animate-rise">
      <h2 className="font-display text-4xl">Settings</h2>
      <p className="text-[var(--muted)]">
        Paste secrets only into <code>backend/.env</code>. Never paste keys into this chat.
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <CardTitle>Sarvam AI</CardTitle>
          <p className="mt-3 text-2xl font-display">{data?.sarvam_configured ? "Configured" : "Missing key"}</p>
          <p className="mt-2 text-sm text-[var(--muted)]">Model: {data?.sarvam_model}</p>
        </Card>
        <Card>
          <CardTitle>Inngest</CardTitle>
          <p className="mt-3 text-2xl font-display">{data?.inngest_configured ? "Configured" : "Local scheduler"}</p>
          <p className="mt-2 text-sm text-[var(--muted)]">{data?.notes?.inngest}</p>
        </Card>
        <Card>
          <CardTitle>Langfuse</CardTitle>
          <p className="mt-3 text-2xl font-display">{data?.langfuse_configured ? "Configured" : "Local logs"}</p>
          <p className="mt-2 text-sm text-[var(--muted)]">{data?.notes?.langfuse}</p>
        </Card>
      </div>
      <Card>
        <CardTitle>Database</CardTitle>
        <p className="mt-2 text-sm">Scheme: {data?.database_url_scheme}</p>
        <p className="mt-1 text-sm">Demo merchant: {data?.demo_merchant_id}</p>
      </Card>
    </div>
  );
}
