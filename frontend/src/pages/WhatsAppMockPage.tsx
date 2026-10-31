import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCheck, Plus, Send, Smile } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("");
}

export function WhatsAppMockPage() {
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const customerParam = params.get("customer");
  const selectedId = customerParam ? Number(customerParam) : null;

  const threads = useQuery({ queryKey: ["wa-threads"], queryFn: api.whatsappThreads });
  const suggestions = useQuery({ queryKey: ["wa-suggestions"], queryFn: api.whatsappSuggestions });
  const thread = useQuery({
    queryKey: ["wa-thread", selectedId],
    queryFn: () => api.whatsappThread(selectedId!),
    enabled: !!selectedId,
  });

  const [draft, setDraft] = useState("");

  useEffect(() => {
    if (!selectedId && threads.data?.threads?.length) {
      setParams({ customer: String(threads.data.threads[0].customer_id) });
    }
  }, [selectedId, threads.data, setParams]);

  const reply = useMutation({
    mutationFn: (body: string) =>
      api.whatsappSimulateReply({ customer_id: selectedId!, body }),
    onSuccess: (r) => {
      setDraft("");
      qc.invalidateQueries({ queryKey: ["wa-thread"] });
      qc.invalidateQueries({ queryKey: ["wa-threads"] });
      qc.invalidateQueries({ queryKey: ["messages"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["escalations"] });
      qc.invalidateQueries({ queryKey: ["followups"] });
      qc.invalidateQueries({ queryKey: ["promises"] });
      if (r.promise_recorded) {
        toast.success("Payment promise auto-recorded from chat", {
          description: `Follow-up on ${r.promise?.promise_date || "scheduled date"} — not marked paid.`,
        });
      } else if (r.intent === "promise" && r.promise && !r.promise.ok) {
        toast.error(r.promise.error || "Could not record promise", {
          description: "If the invoice is already paid/closed, reload demo data and try again.",
        });
      } else if (r.intent === "payment_claim" || (r.escalated && r.intent === "payment_claim")) {
        toast.message("Customer claims paid — upload proof, then match ledger CSV", {
          description: "Chat/screenshot never marks invoice paid.",
        });
      } else if (r.escalated) {
        toast.error("Escalated to merchant — automation paused", {
          description: "Open Collections for the merchant inbox alert.",
        });
      } else {
        toast.success("Customer reply added to mock chat");
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const uploadEvidence = useMutation({
    mutationFn: (file: File) => api.whatsappUploadEvidence(selectedId!, file),
    onSuccess: (r) => {
      qc.invalidateQueries();
      if (r.ok) {
        toast.success(`Proof from ${r.customer_name || "chat customer"}`, {
          description: `${r.invoice_id || "invoice"} · still unpaid until bank CSV matches on Reconciliation.`,
        });
      } else toast.error(r.error || "Upload failed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const contactName = thread.data?.customer_name || "Select a chat";
  const statusLine = thread.data?.status_line || "sandbox demo";
  const bubbles = thread.data?.messages || [];

  const emptyHint = useMemo(
    () =>
      !threads.data?.threads?.length
        ? "Approve a reminder on Approvals first — it will appear here as a WhatsApp mock."
        : "Pick a debtor chat on the left.",
    [threads.data]
  );

  return (
    <div className="space-y-4 animate-rise">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-4xl">WhatsApp mock</h2>
          <p className="mt-1 text-[var(--muted)]">
            Promises (“pay tomorrow / 2 days later”) auto-record. “I paid” → evidence upload + ledger match. Refusal → merchant inbox.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="secondary">
            <Link to="/approvals">Go to Approvals</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link to="/collections">Merchant escalations</Link>
          </Button>
        </div>
      </div>

      {thread.data?.case_status === "promised" && (
        <Card className="border-teal-200 bg-teal-50/70">
          <CardTitle>Payment promise recorded</CardTitle>
          <p className="mt-2 text-sm text-[var(--muted)]">
            {thread.data?.hint ||
              "Promise auto-captured from WhatsApp. Follow-up is scheduled. Invoice stays unpaid until a matched payment hits the ledger."}
          </p>
          <Button asChild className="mt-3" size="sm" variant="secondary">
            <Link to="/collections">View promises & follow-ups</Link>
          </Button>
        </Card>
      )}

      {(thread.data?.merchant_escalation ||
        thread.data?.case_status === "escalated" ||
        thread.data?.case_status === "disputed") && (
        <Card className="border-amber-300 bg-amber-50/80">
          <CardTitle>Escalated to merchant</CardTitle>
          <p className="mt-2 whitespace-pre-wrap text-sm">
            {thread.data?.merchant_escalation?.body ||
              `Case status: ${thread.data?.case_status}. Automation paused — decide the next step in Collections.`}
          </p>
          <p className="mt-2 text-sm text-[var(--muted)]">
            If they claim payment: use <strong>+</strong> in the phone to upload a screenshot, then import the matching bank CSV on Reconciliation.
          </p>
          <Button asChild className="mt-3" size="sm">
            <Link to="/collections">Open Collections inbox</Link>
          </Button>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="p-0 overflow-hidden">
          <div className="border-b border-[var(--line)] bg-[#10251f] px-4 py-3 text-sm text-teal-50">
            Chats
          </div>
          <ul className="max-h-[70vh] overflow-y-auto">
            {(threads.data?.threads || []).map((t: any) => (
              <li key={t.customer_id}>
                <button
                  type="button"
                  onClick={() => setParams({ customer: String(t.customer_id) })}
                  className={cn(
                    "flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-black/[0.04]",
                    selectedId === t.customer_id && "bg-teal-50"
                  )}
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#0f766e] text-sm font-semibold text-white">
                    {initials(t.customer_name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{t.customer_name}</span>
                    <span className="block truncate text-xs text-[var(--muted)]">{t.last_preview}</span>
                  </span>
                </button>
              </li>
            ))}
            {!threads.data?.threads?.length && (
              <li className="px-4 py-8 text-sm text-[var(--muted)]">{emptyHint}</li>
            )}
          </ul>
        </Card>

        <div className="flex justify-center lg:justify-start">
          <div className="wa-phone relative w-full max-w-[390px] overflow-hidden rounded-[2rem] border-[10px] border-[#1a1a1a] bg-[#0b141a] shadow-[0_24px_60px_rgba(20,35,28,0.35)]">
            <div className="flex items-center justify-between bg-[#0b141a] px-5 pb-1 pt-3 text-[11px] font-medium text-white">
              <span>9:41</span>
              <span className="mx-auto h-1.5 w-20 rounded-full bg-white/20" />
              <span className="tracking-tight">▮▮▮</span>
            </div>

            <div className="flex items-center gap-3 bg-[#1f2c34] px-3 py-2.5 text-white">
              <span className="text-teal-200/80">‹</span>
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#6b5b95] text-sm font-semibold">
                {initials(contactName)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[15px] font-semibold leading-tight">{contactName}</div>
                <div className="truncate text-[11px] text-white/60">{statusLine}</div>
              </div>
              <span className="text-white/70 text-xs">📹  📞</span>
            </div>

            <div
              className="wa-wallpaper flex h-[520px] flex-col gap-2 overflow-y-auto px-3 py-3"
              style={{
                backgroundColor: "#0b141a",
                backgroundImage:
                  "radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px)",
                backgroundSize: "18px 18px",
              }}
            >
              {!selectedId && (
                <p className="m-auto max-w-[240px] text-center text-sm text-white/50">{emptyHint}</p>
              )}
              {selectedId && !bubbles.length && (
                <p className="m-auto max-w-[240px] text-center text-sm text-white/50">
                  No messages yet. Approve a draft reminder for this debtor.
                </p>
              )}
              {bubbles.map((m: any) => {
                const mine = m.role === "me";
                return (
                  <div
                    key={m.id}
                    className={cn("flex", mine ? "justify-end" : "justify-start")}
                  >
                    <div
                      className={cn(
                        "max-w-[82%] rounded-lg px-2.5 py-1.5 text-[13.5px] leading-snug shadow-sm",
                        mine ? "rounded-tr-sm bg-[#005c4b] text-white" : "rounded-tl-sm bg-[#1f2c34] text-white"
                      )}
                    >
                      <div className="whitespace-pre-wrap">{m.body}</div>
                      <div className="mt-0.5 flex items-center justify-end gap-1 text-[10px] text-white/55">
                        <span>{m.time}</span>
                        {mine && m.ticks === "read" && <CheckCheck size={12} className="text-sky-300" />}
                        {mine && m.ticks === "sent" && <Check size={12} />}
                        {mine && m.status === "pending_approval" && (
                          <span className="text-amber-300">pending</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center gap-2 bg-[#1f2c34] px-2 py-2">
              <button type="button" className="rounded-full p-2 text-white/70" aria-label="emoji">
                <Smile size={18} />
              </button>
              <label
                className={cn(
                  "cursor-pointer rounded-full p-2 text-white/70",
                  (!selectedId || uploadEvidence.isPending) && "pointer-events-none opacity-40"
                )}
                title="Upload payment screenshot (evidence only)"
              >
                <Plus size={18} />
                <input
                  type="file"
                  accept="image/*,.pdf"
                  className="hidden"
                  disabled={!selectedId || uploadEvidence.isPending}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadEvidence.mutate(f);
                    e.target.value = "";
                  }}
                />
              </label>
              <input
                className="min-w-0 flex-1 rounded-full bg-[#2a3942] px-3 py-2 text-sm text-white placeholder:text-white/40 outline-none"
                placeholder="Simulate debtor reply…"
                value={draft}
                disabled={!selectedId}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && draft.trim() && selectedId) {
                    reply.mutate(draft.trim());
                  }
                }}
              />
              <button
                type="button"
                className="rounded-full bg-[#00a884] p-2 text-white disabled:opacity-40"
                disabled={!selectedId || !draft.trim() || reply.isPending}
                onClick={() => draft.trim() && reply.mutate(draft.trim())}
                aria-label="send"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <Card>
        <CardTitle>Quick debtor replies (demo)</CardTitle>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Promise phrases auto-record a promise. “I paid” escalates + use + to attach proof. Still close only via matched txn CSV.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {(suggestions.data?.replies || []).map((r: string) => (
            <Button
              key={r}
              variant="secondary"
              disabled={!selectedId || reply.isPending}
              onClick={() => reply.mutate(r)}
            >
              {r.slice(0, 48)}…
            </Button>
          ))}
        </div>
      </Card>
    </div>
  );
}
