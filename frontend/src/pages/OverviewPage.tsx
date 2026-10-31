import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Line,
  LineChart,
} from "recharts";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardTitle, CardValue } from "@/components/ui/card";

export function OverviewPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const loadDemo = useMutation({
    mutationFn: api.loadDemo,
    onSuccess: (res) => {
      toast.success(`Demo loaded · outstanding ${res.outstanding_display || res.outstanding_paise}`);
      qc.invalidateQueries();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) return <p className="text-[var(--muted)]">Loading dashboard…</p>;

  const aging = Object.entries(data?.aging || {}).map(([k, v]: any) => ({
    bucket: k.replace("_", "-"),
    amount: (v.paise || 0) / 100,
  }));

  return (
    <div className="space-y-6 animate-rise">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Merchant overview</p>
          <h2 className="font-display text-4xl mt-1">Receivables command center</h2>
          <p className="mt-2 max-w-2xl text-[var(--muted)]">
            Ledger facts drive balances. The AI teammate selects tools and drafts language — you approve
            consequential messages.
          </p>
        </div>
        <Button onClick={() => loadDemo.mutate()} disabled={loadDemo.isPending}>
          {loadDemo.isPending ? "Loading…" : "Load demo data"}
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card>
          <CardTitle>Outstanding</CardTitle>
          <CardValue>{data?.outstanding ?? "—"}</CardValue>
        </Card>
        <Card>
          <CardTitle>Overdue</CardTitle>
          <CardValue>{data?.overdue ?? "—"}</CardValue>
        </Card>
        <Card>
          <CardTitle>Invoices</CardTitle>
          <CardValue>{data?.total_invoices ?? 0}</CardValue>
          <p className="mt-2 text-xs text-[var(--muted)]">
            Paid {data?.fully_paid} · Partial {data?.partially_paid} · Unpaid {data?.unpaid}
          </p>
        </Card>
        <Card>
          <CardTitle>Pending approvals</CardTitle>
          <CardValue>{data?.pending_approvals ?? 0}</CardValue>
        </Card>
        <Card>
          <CardTitle>Unmatched txns</CardTitle>
          <CardValue>{data?.unmatched_transactions ?? 0}</CardValue>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>Overdue aging (₹)</CardTitle>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={aging}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(20,35,28,0.08)" />
                <XAxis dataKey="bucket" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="amount" fill="#0f766e" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardTitle>Payment collection trend</CardTitle>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={(data?.payment_trend || []).map((d: any) => ({ ...d, amt: d.amount_paise / 100 }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(20,35,28,0.08)" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="amt" stroke="#c47a12" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>Customer balances</CardTitle>
          <ul className="mt-3 space-y-2">
            {(data?.customer_balances || []).map((c: any) => (
              <li key={c.customer} className="flex justify-between border-b border-[var(--line)] py-2 text-sm">
                <span>{c.customer}</span>
                <strong>{c.outstanding}</strong>
              </li>
            ))}
            {!data?.customer_balances?.length && (
              <li className="text-sm text-[var(--muted)]">No outstanding balances. Load demo data to begin.</li>
            )}
          </ul>
        </Card>
        <Card>
          <CardTitle>Recent activity</CardTitle>
          <ul className="mt-3 max-h-72 space-y-2 overflow-auto">
            {(data?.recent_activity || []).map((a: any) => (
              <li key={a.id} className="rounded-xl bg-black/[0.03] px-3 py-2 text-sm">
                <div className="font-medium">{a.action}</div>
                <div className="text-[var(--muted)]">{a.detail}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
