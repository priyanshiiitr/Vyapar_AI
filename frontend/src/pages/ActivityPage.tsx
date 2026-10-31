import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Card, CardTitle } from "@/components/ui/card";

export function ActivityPage() {
  const { data } = useQuery({ queryKey: ["activity"], queryFn: api.activity });
  return (
    <div className="space-y-4 animate-rise">
      <h2 className="font-display text-4xl">Activity log</h2>
      <Card>
        <CardTitle>Audit trail</CardTitle>
        <ul className="mt-4 space-y-2">
          {(data?.events || []).map((e: any) => (
            <li key={e.id} className="rounded-xl border border-[var(--line)] bg-white/60 px-3 py-3 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <strong>{e.action}</strong>
                <span className="text-[var(--muted)]">{e.created_at}</span>
              </div>
              <div className="text-[var(--muted)]">
                {e.entity_type}:{e.entity_id} · {e.actor}
              </div>
              <div>{e.detail}</div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
