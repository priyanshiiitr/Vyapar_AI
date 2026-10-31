import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";

export function ApprovalsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data } = useQuery({ queryKey: ["approvals"], queryFn: api.approvals });
  const messages = useQuery({ queryKey: ["messages"], queryFn: api.messages });
  const [edits, setEdits] = useState<Record<number, string>>({});

  const approve = useMutation({
    mutationFn: ({ id, body }: { id: number; body?: string }) => api.approve(id, body),
    onSuccess: (r) => {
      toast.success(r.note || "Approved — opening WhatsApp mock");
      qc.invalidateQueries();
      if (r.customer_id) {
        navigate(`/whatsapp?customer=${r.customer_id}`);
      } else {
        navigate("/whatsapp");
      }
    },
  });
  const reject = useMutation({
    mutationFn: (id: number) => api.reject(id, "Rejected by merchant"),
    onSuccess: () => {
      toast.message("Rejected");
      qc.invalidateQueries();
    },
  });

  return (
    <div className="space-y-4 animate-rise">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-4xl">Approvals</h2>
          <p className="text-[var(--muted)]">
            Approve drafts to “send” them into the WhatsApp mock. No real WhatsApp/SMS/email leaves this laptop.
          </p>
        </div>
        <Button asChild variant="secondary">
          <Link to="/whatsapp">Open WhatsApp mock</Link>
        </Button>
      </div>
      <div className="space-y-3">
        {(data?.approvals || []).map((m: any) => (
          <Card key={m.id}>
            <CardTitle>
              #{m.id} · {m.invoice_id} · {m.customer || "Customer"} · {m.language} / {m.tone}
            </CardTitle>
            <textarea
              className="mt-3 min-h-28 w-full rounded-xl border border-[var(--line)] bg-white p-3 text-sm"
              value={edits[m.id] ?? m.body}
              onChange={(e) => setEdits((s) => ({ ...s, [m.id]: e.target.value }))}
            />
            <div className="mt-3 flex gap-2">
              <Button onClick={() => approve.mutate({ id: m.id, body: edits[m.id] ?? m.body })}>
                Approve → WhatsApp mock
              </Button>
              <Button variant="secondary" onClick={() => reject.mutate(m.id)}>
                Reject
              </Button>
            </div>
          </Card>
        ))}
        {!data?.approvals?.length && (
          <Card>
            <p className="text-sm text-[var(--muted)]">
              No pending approvals. Create a reminder from Collections or AI, then approve it here.
            </p>
          </Card>
        )}
      </div>
      <Card>
        <CardTitle>Message history</CardTitle>
        <ul className="mt-3 space-y-2 text-sm">
          {(messages.data?.messages || []).map((m: any) => (
            <li key={m.id} className="rounded-xl bg-black/[0.03] px-3 py-2">
              <div className="font-medium">
                #{m.id} · {m.status}
                {m.customer ? ` · ${m.customer}` : ""}
                {m.invoice_id ? ` · ${m.invoice_id}` : ""}
              </div>
              <div className="text-[var(--muted)]">{m.sandbox_note || m.body.slice(0, 120)}</div>
              {m.customer_id && m.status === "sandbox_sent" && (
                <Link
                  className="mt-1 inline-block text-xs font-semibold text-[var(--teal)]"
                  to={`/whatsapp?customer=${m.customer_id}`}
                >
                  View in WhatsApp mock →
                </Link>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
