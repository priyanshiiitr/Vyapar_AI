import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";

export function EvaluationPage() {
  const qc = useQueryClient();
  const latest = useQuery({ queryKey: ["evaluation"], queryFn: api.latestEvaluation });
  const run = useMutation({
    mutationFn: api.runEvaluation,
    onSuccess: () => {
      toast.success("Evaluation completed with measured values");
      qc.invalidateQueries({ queryKey: ["evaluation"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const metrics = latest.data?.metrics || [];
  const chart = metrics
    .filter((m: any) => typeof m.numerator === "number" && typeof m.denominator === "number" && m.denominator > 0)
    .map((m: any) => ({
      name: m.metric_key.replaceAll("_", " "),
      rate: Math.round((m.numerator / m.denominator) * 1000) / 10,
    }));

  return (
    <div className="space-y-4 animate-rise">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-4xl">Evaluation</h2>
          <p className="text-[var(--muted)]">
            Targets vs measured values. Numerators and denominators shown. Synthetic corpus uses Faker
            (en_IN). No fabricated scores.
          </p>
        </div>
        <Button onClick={() => run.mutate()} disabled={run.isPending}>
          {run.isPending ? "Running…" : "Run evaluation"}
        </Button>
      </div>

      <Card>
        <CardTitle>Metric chart (where ratio applies)</CardTitle>
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" hide />
              <YAxis />
              <Tooltip />
              <Bar dataKey="rate" fill="#0f766e" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-3 md:grid-cols-2">
        {metrics.map((m: any) => (
          <Card key={m.metric_key}>
            <CardTitle>{m.metric_name}</CardTitle>
            <p className="mt-2 font-display text-3xl">{m.value ?? "N/A"}</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Target: {m.target} · Numerator: {m.numerator ?? "N/A"} / Denominator: {m.denominator ?? "N/A"}
            </p>
            <p className="mt-1 text-sm font-semibold">
              {m.passed == null ? "N/A" : m.passed ? "PASS" : "FAIL"}
            </p>
          </Card>
        ))}
        {!metrics.length && (
          <Card>
            <p className="text-sm text-[var(--muted)]">No evaluation run yet.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
