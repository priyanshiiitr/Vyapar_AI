import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Papa from "papaparse";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";

type LedgerDraft = {
  invoice_id: string;
  customer_name: string;
  customer_phone: string;
  amount: string;
  amount_paid: string;
  balance_due: string;
  invoice_date: string;
  due_date: string;
  description: string;
};

const emptyDraft = (): LedgerDraft => ({
  invoice_id: "",
  customer_name: "",
  customer_phone: "",
  amount: "",
  amount_paid: "",
  balance_due: "",
  invoice_date: "",
  due_date: "",
  description: "",
});

function draftFromNormalized(n: any): LedgerDraft {
  return {
    invoice_id: String(n?.invoice_id || ""),
    customer_name: String(n?.customer_name || ""),
    customer_phone: String(n?.customer_phone || ""),
    amount: n?.amount != null ? String(n.amount) : "",
    amount_paid: n?.amount_paid != null ? String(n.amount_paid) : "",
    balance_due: n?.balance_due != null ? String(n.balance_due) : "",
    invoice_date: String(n?.invoice_date || ""),
    due_date: String(n?.due_date || ""),
    description: String(n?.description || ""),
  };
}

export function ReconciliationPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["transactions"], queryFn: api.transactions });
  const waEvidence = useQuery({
    queryKey: ["wa-payment-evidence"],
    queryFn: api.whatsappPaymentEvidence,
  });
  const [preview, setPreview] = useState<any>(null);
  const [docResult, setDocResult] = useState<any>(null);
  const [docBusy, setDocBusy] = useState(false);
  const [draft, setDraft] = useState<LedgerDraft>(emptyDraft());
  const [ledgerResult, setLedgerResult] = useState<any>(null);

  const uploadInv = useMutation({
    mutationFn: api.uploadInvoices,
    onSuccess: (r) => {
      toast.success(`Invoices imported: ${r.created}`);
      qc.invalidateQueries();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const uploadTxn = useMutation({
    mutationFn: api.uploadTransactions,
    onSuccess: (r) => {
      toast.success(`Transactions imported: ${r.created}`);
      qc.invalidateQueries();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const run = useMutation({
    mutationFn: api.runReconciliation,
    onSuccess: (r) => {
      toast.success(`Reconciled ${r.processed} transactions`);
      qc.invalidateQueries();
    },
  });
  const confirmLedger = useMutation({
    mutationFn: () =>
      api.confirmDocLedger({
        invoice_id: draft.invoice_id.trim(),
        customer_name: draft.customer_name.trim(),
        customer_phone: draft.customer_phone.trim() || null,
        amount: draft.amount.trim(),
        amount_paid: draft.amount_paid.trim() || null,
        balance_due: draft.balance_due.trim() || null,
        invoice_date: draft.invoice_date.trim(),
        due_date: draft.due_date.trim(),
        description: draft.description.trim() || null,
      }),
    onSuccess: (r) => {
      setLedgerResult(r);
      if (r.ok) {
        toast.success(
          r.overdue
            ? `Ledger overdue created: ${r.invoice_id} · ${r.outstanding}`
            : `Ledger invoice created: ${r.invoice_id}`
        );
        qc.invalidateQueries();
      } else {
        toast.error(r.error || "Could not create ledger invoice");
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function onFile(kind: "invoices" | "transactions", file?: File | null) {
    if (!file) return;
    const text = await file.text();
    const parsed = Papa.parse(text, { header: true });
    setPreview({ kind, rows: parsed.data.slice(0, 8), fields: parsed.meta.fields });
    if (kind === "invoices") uploadInv.mutate(file);
    else uploadTxn.mutate(file);
  }

  async function importTxn803() {
    const csv = await api.txn803();
    const blob = new Blob([csv], { type: "text/csv" });
    const file = new File([blob], "txn_803.csv", { type: "text/csv" });
    uploadTxn.mutate(file);
  }

  async function importClearCsv(path: string, filename: string) {
    const text = await fetch(path).then((r) => r.text());
    const file = new File([text], filename, { type: "text/csv" });
    setPreview({ kind: "transactions", rows: Papa.parse(text, { header: true }).data.slice(0, 8) });
    uploadTxn.mutate(file);
  }

  async function onDocFile(file?: File | null) {
    if (!file) return;
    setDocBusy(true);
    setDocResult(null);
    setLedgerResult(null);
    try {
      const res = await api.extractDoc(file);
      setDocResult(res);
      if (res.ok) {
        setDraft(draftFromNormalized(res.normalized || {}));
        toast.success("Extracted — review fields, then create ledger invoice");
      } else toast.error(res.error || "Document AI failed");
    } catch (e: any) {
      toast.error(e.message || "Document AI error");
    } finally {
      setDocBusy(false);
    }
  }

  function setField<K extends keyof LedgerDraft>(key: K, value: string) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  const canConfirm =
    !!draft.invoice_id.trim() &&
    !!draft.customer_name.trim() &&
    !!draft.amount.trim() &&
    !!draft.invoice_date.trim() &&
    !!draft.due_date.trim();

  return (
    <div className="space-y-4 animate-rise">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-4xl">Reconciliation</h2>
          <p className="text-[var(--muted)]">
            CSV evidence is authoritative. Exact invoice refs auto-match; RapidFuzz handles messy names when amount is exact.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="cursor-pointer">
            <span className="inline-flex h-10 items-center rounded-xl border border-[var(--line)] bg-white/80 px-4 text-sm font-semibold">
              Upload invoices CSV
            </span>
            <input type="file" accept=".csv" className="hidden" onChange={(e) => onFile("invoices", e.target.files?.[0])} />
          </label>
          <label className="cursor-pointer">
            <span className="inline-flex h-10 items-center rounded-xl border border-[var(--line)] bg-white/80 px-4 text-sm font-semibold">
              Upload transactions CSV
            </span>
            <input type="file" accept=".csv" className="hidden" onChange={(e) => onFile("transactions", e.target.files?.[0])} />
          </label>
          <Button variant="secondary" onClick={() => importTxn803()}>
            Import TXN-803 (demo)
          </Button>
          <Button onClick={() => run.mutate()}>Run reconciliation</Button>
        </div>
      </div>

      <Card>
        <CardTitle>WhatsApp payment proofs (from chat)</CardTitle>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Uploader name is always the <strong>WhatsApp chat customer</strong> (e.g. Kumar Mart), never guessed from the PNG
          filename. Match a bank CSV for that invoice to mark paid.
        </p>
        <ul className="mt-3 space-y-3">
          {(waEvidence.data?.evidence || []).map((e: any) => (
            <li key={e.id} className="rounded-xl border border-[var(--line)] bg-white/70 p-3">
              <p className="font-semibold">
                {e.customer_name}
                {e.invoice_id ? ` · ${e.invoice_id}` : ""}
                {e.outstanding ? ` · ${e.outstanding}` : ""}
              </p>
              <p className="mt-1 text-xs text-[var(--muted)]">
                File on disk: {e.filename || "—"} (filename is not the customer identity)
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {e.whatsapp_path && (
                  <Button asChild size="sm" variant="secondary">
                    <Link to={e.whatsapp_path}>Open WhatsApp chat</Link>
                  </Button>
                )}
                {e.download_path && (
                  <a
                    className="inline-flex h-8 items-center rounded-xl border border-[var(--line)] bg-white px-3 text-xs font-semibold"
                    href={e.download_path}
                    download
                  >
                    View uploaded proof
                  </a>
                )}
                {e.invoice_id === "R-106" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => importClearCsv("/api/demo/txn-r106-clear.csv", "txn_r106_clear.csv")}
                  >
                    Upload Kumar Mart bank CSV (R-106)
                  </Button>
                )}
                {e.invoice_id === "R-104" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => importClearCsv("/api/demo/txn-r104-clear.csv", "txn_r104_clear.csv")}
                  >
                    Upload ABC Stores bank CSV (R-104)
                  </Button>
                )}
                {e.invoice_id === "SBH/26-27/104" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => importClearCsv("/api/demo/txn-sbh104-clear.csv", "txn_sbh_104_clear.csv")}
                  >
                    Upload Sharma bank CSV
                  </Button>
                )}
                <Button size="sm" onClick={() => run.mutate()}>
                  Run reconciliation
                </Button>
              </div>
            </li>
          ))}
          {!waEvidence.data?.evidence?.length && (
            <li className="text-sm text-[var(--muted)]">
              No WhatsApp proofs yet. Open a debtor chat → tap + → upload that customer’s proof PNG.
            </li>
          )}
        </ul>
      </Card>

      <Card>
        <CardTitle>Sample proof downloads (use the matching chat)</CardTitle>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Download the PNG for the <em>same</em> customer you have open in WhatsApp. Uploading ABC’s file in Kumar Mart’s
          chat still attributes the upload to <strong>Kumar Mart</strong>.
        </p>
        <div className="mt-3 grid gap-3 lg:grid-cols-3">
          <div className="rounded-xl border border-[var(--line)] bg-white/60 p-3">
            <p className="font-semibold">ABC Stores · R-104 · ₹15,000</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <a
                className="inline-flex h-9 items-center rounded-xl border border-[var(--line)] bg-white px-3 text-sm font-semibold"
                href="/api/demo/payment-proof/r104"
                download
              >
                Download proof PNG
              </a>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => importClearCsv("/api/demo/txn-r104-clear.csv", "txn_r104_clear.csv")}
              >
                Bank CSV
              </Button>
            </div>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-white/60 p-3">
            <p className="font-semibold">Kumar Mart · R-106 · ₹18,000</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <a
                className="inline-flex h-9 items-center rounded-xl border border-[var(--line)] bg-white px-3 text-sm font-semibold"
                href="/api/demo/payment-proof/r106"
                download
              >
                Download proof PNG
              </a>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => importClearCsv("/api/demo/txn-r106-clear.csv", "txn_r106_clear.csv")}
              >
                Bank CSV
              </Button>
            </div>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-white/60 p-3">
            <p className="font-semibold">Sharma · SBH/26-27/104 · ₹15,000</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <a
                className="inline-flex h-9 items-center rounded-xl border border-[var(--line)] bg-white px-3 text-sm font-semibold"
                href="/api/demo/payment-proof/sbh104"
                download
              >
                Download proof PNG
              </a>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => importClearCsv("/api/demo/txn-sbh104-clear.csv", "txn_sbh_104_clear.csv")}
              >
                Bank CSV
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardTitle>Sarvam Document AI → ledger</CardTitle>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Extract with Sarvam Doc AI, review (especially total vs balance due / paid), then one click creates a real
          ledger invoice and open collection case when overdue.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <a
            className="inline-flex h-10 items-center rounded-xl border border-[var(--line)] bg-white/80 px-4 text-sm font-semibold"
            href="/api/doc-ai/sample"
          >
            Simple sample PDF
          </a>
          <a
            className="inline-flex h-10 items-center rounded-xl border border-[var(--line)] bg-white/80 px-4 text-sm font-semibold"
            href="/api/doc-ai/sample-complex"
          >
            Complex GST overdue PDF
          </a>
          <label className="cursor-pointer">
            <span className="inline-flex h-10 items-center rounded-xl bg-[var(--teal)] px-4 text-sm font-semibold text-white">
              {docBusy ? "Extracting…" : "Extract invoice fields"}
            </span>
            <input
              type="file"
              accept=".pdf,image/*"
              className="hidden"
              disabled={docBusy}
              onChange={(e) => onDocFile(e.target.files?.[0])}
            />
          </label>
        </div>

        {(docResult?.ok || draft.invoice_id) && (
          <div className="mt-4 space-y-3 rounded-xl border border-[var(--line)] bg-white/60 p-4">
            <p className="text-sm font-semibold">Review before ledger write</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  ["invoice_id", "Invoice ID"],
                  ["customer_name", "Customer name"],
                  ["customer_phone", "Customer phone"],
                  ["amount", "Invoice total (₹)"],
                  ["amount_paid", "Amount paid (₹)"],
                  ["balance_due", "Balance due (₹)"],
                  ["invoice_date", "Invoice date"],
                  ["due_date", "Due date"],
                  ["description", "Description"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="block text-xs text-[var(--muted)] sm:col-span-1">
                  {label}
                  <input
                    className="mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)]"
                    value={draft[key]}
                    onChange={(e) => setField(key, e.target.value)}
                  />
                </label>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                disabled={!canConfirm || confirmLedger.isPending}
                onClick={() => confirmLedger.mutate()}
              >
                {confirmLedger.isPending ? "Creating…" : "Confirm → create ledger invoice"}
              </Button>
              {ledgerResult?.ok && (
                <>
                  <span className="text-sm text-[var(--ok)]">
                    {ledgerResult.invoice_id} · outstanding {ledgerResult.outstanding}
                    {ledgerResult.overdue ? ` · ${ledgerResult.days_overdue}d overdue` : ""}
                  </span>
                  <Button asChild variant="secondary" size="sm">
                    <Link to="/collections">Open Collections</Link>
                  </Button>
                  <Button asChild variant="secondary" size="sm">
                    <Link to="/invoices">View Invoices</Link>
                  </Button>
                </>
              )}
              {ledgerResult && !ledgerResult.ok && (
                <span className="text-sm text-[var(--danger)]">{ledgerResult.error}</span>
              )}
            </div>
          </div>
        )}

        {docResult && (
          <pre className="mt-3 max-h-56 overflow-auto rounded-xl bg-black/[0.04] p-3 text-xs">
            {JSON.stringify(docResult, null, 2)}
          </pre>
        )}
      </Card>

      {preview && (
        <Card>
          <CardTitle>CSV preview ({preview.kind})</CardTitle>
          <pre className="mt-3 overflow-auto rounded-xl bg-black/[0.04] p-3 text-xs">
            {JSON.stringify(preview.rows, null, 2)}
          </pre>
        </Card>
      )}

      <Card>
        <CardTitle>Transactions</CardTitle>
        <div className="mt-4 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-[var(--muted)]">
              <tr>
                <th className="py-2">Txn</th>
                <th>Reference</th>
                <th>Amount</th>
                <th>Customer</th>
                <th>Status</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {(data?.transactions || []).map((t: any) => (
                <tr key={t.transaction_id} className="border-t border-[var(--line)]">
                  <td className="py-3 font-semibold">{t.transaction_id}</td>
                  <td>{t.reference || "—"}</td>
                  <td>{t.amount}</td>
                  <td>{t.customer_name}</td>
                  <td>{t.status}</td>
                  <td>{t.evidence_source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
