import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";

function nextFridayISO() {
  const d = new Date();
  const day = d.getDay();
  const diff = (5 - day + 7) % 7 || 7;
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

export function CollectionsPage() {
  const qc = useQueryClient();
  const cases = useQuery({ queryKey: ["cases"], queryFn: api.cases });
  const promises = useQuery({ queryKey: ["promises"], queryFn: api.promises });
  const followups = useQuery({ queryKey: ["followups"], queryFn: api.followups });
  const escalations = useQuery({ queryKey: ["escalations"], queryFn: api.escalations });

  const reminder = useMutation({
    mutationFn: () =>
      api.createReminder({ invoice_id: "R-104", language: "hinglish", tone: "polite" }),
    onSuccess: () => {
      toast.success("Hinglish reminder draft created for approval");
      qc.invalidateQueries();
    },
  });
  const promise = useMutation({
    mutationFn: () =>
      api.recordPromise({
        invoice_id: "R-104",
        promise_date: nextFridayISO(),
        customer_statement: "Will pay on Friday",
      }),
    onSuccess: () => {
      toast.success("Promise recorded + follow-up scheduled");
      qc.invalidateQueries();
    },
  });
  const processDue = useMutation({
    mutationFn: api.processDue,
    onSuccess: (r) => {
      toast.success(`Processed ${r.processed} due follow-ups`);
      qc.invalidateQueries();
    },
  });

  return (
    <div className="space-y-4 animate-rise">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-4xl">Collections</h2>
          <p className="text-[var(--muted)]">
            Promises persist. Follow-ups never auto-send. “Can’t pay” / dispute replies escalate here for you.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => reminder.mutate()}>Draft Hinglish reminder (R-104)</Button>
          <Button variant="secondary" onClick={() => promise.mutate()}>
            Record Friday promise (R-104)
          </Button>
          <Button variant="secondary" onClick={() => processDue.mutate()}>
            Process due follow-ups now
          </Button>
          <Button asChild variant="secondary">
            <Link to="/whatsapp">WhatsApp mock</Link>
          </Button>
        </div>
      </div>

      {(escalations.data?.escalations || []).length > 0 && (
        <Card className="border-amber-300/80 bg-amber-50/70">
          <CardTitle>Merchant escalations</CardTitle>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Debtor refused or disputed — automation paused. Ledger unpaid until a matched payment arrives.
          </p>
          <ul className="mt-3 space-y-2 text-sm">
            {(escalations.data?.escalations || []).map((e: any) => (
              <li key={e.id} className="rounded-xl border border-amber-200 bg-white/80 px-3 py-2 whitespace-pre-wrap">
                <div className="font-semibold">
                  #{e.id} · {e.invoice_id || "invoice?"}
                  {e.customer_id ? (
                    <>
                      {" · "}
                      <Link className="text-[var(--teal)]" to={`/whatsapp?customer=${e.customer_id}`}>
                        Open chat
                      </Link>
                    </>
                  ) : null}
                </div>
                <div className="mt-1 text-[var(--ink)]">{e.body}</div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <CardTitle>Collection cases</CardTitle>
        <div className="mt-3 overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-[var(--muted)]">
              <tr>
                <th className="py-2 text-left">Invoice</th>
                <th className="text-left">Customer</th>
                <th className="text-left">Outstanding</th>
                <th className="text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {(cases.data?.cases || []).map((c: any) => (
                <tr key={c.id} className="border-t border-[var(--line)]">
                  <td className="py-3 font-semibold">{c.invoice_id}</td>
                  <td>{c.customer}</td>
                  <td>{c.outstanding}</td>
                  <td
                    className={
                      c.status === "escalated" || c.status === "disputed"
                        ? "font-semibold text-amber-800"
                        : undefined
                    }
                  >
                    {c.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>Payment promises</CardTitle>
          <ul className="mt-3 space-y-2 text-sm">
            {(promises.data?.promises || []).map((p: any) => (
              <li key={p.id} className="rounded-xl bg-black/[0.03] px-3 py-2">
                <div className="font-medium">
                  #{p.id} · {p.invoice_id || `inv#${p.invoice_pk}`} · {p.promised} · {p.promise_date} ·{" "}
                  {p.status}
                </div>
                {p.statement ? (
                  <div className="mt-1 text-xs text-[var(--muted)]">“{p.statement}”</div>
                ) : null}
              </li>
            ))}
            {!promises.data?.promises?.length && (
              <li className="text-sm text-[var(--muted)]">
                No promises yet. In WhatsApp mock, reply “I will pay tomorrow” — it auto-records here.
              </li>
            )}
          </ul>
        </Card>
        <Card>
          <CardTitle>Follow-ups</CardTitle>
          <ul className="mt-3 space-y-2 text-sm">
            {(followups.data?.followups || []).map((f: any) => (
              <li key={f.id} className="rounded-xl bg-black/[0.03] px-3 py-2">
                {f.invoice_id} · {f.followup_date} · {f.status}
                {f.inngest_event_id ? ` · inngest:${f.inngest_event_id}` : ""}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
