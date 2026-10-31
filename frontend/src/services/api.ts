const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return (await res.text()) as T;
}

export const api = {
  dashboard: () => request<any>("/api/dashboard"),
  activity: () => request<any>("/api/activity"),
  invoices: (status?: string) =>
    request<any>(`/api/invoices${status ? `?status=${status}` : ""}`),
  loadDemo: () => request<any>("/api/demo/load", { method: "POST" }),
  resetDemo: () => request<any>("/api/demo/reset", { method: "POST" }),
  transactions: () => request<any>("/api/reconciliation/transactions"),
  uploadInvoices: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<any>("/api/reconciliation/upload-invoices", { method: "POST", body: fd });
  },
  uploadTransactions: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<any>("/api/reconciliation/upload-transactions", { method: "POST", body: fd });
  },
  previewCsv: (kind: string, file: File) => {
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file);
    return request<any>("/api/reconciliation/preview", { method: "POST", body: fd });
  },
  runReconciliation: () => request<any>("/api/reconciliation/run", { method: "POST" }),
  cases: () => request<any>("/api/collections/cases"),
  approvals: () => request<any>("/api/collections/approvals"),
  messages: () => request<any>("/api/collections/messages"),
  createReminder: (body: any) =>
    request<any>("/api/collections/reminders", { method: "POST", body: JSON.stringify(body) }),
  approve: (id: number, edited_body?: string) =>
    request<any>(`/api/collections/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ edited_body }),
    }),
  reject: (id: number, reason?: string) =>
    request<any>(`/api/collections/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  promises: () => request<any>("/api/collections/promises"),
  recordPromise: (body: any) =>
    request<any>("/api/collections/promises", { method: "POST", body: JSON.stringify(body) }),
  followups: () => request<any>("/api/collections/followups"),
  escalations: () => request<any>("/api/collections/escalations"),
  processDue: () => request<any>("/api/scheduler/process-due", { method: "POST" }),
  chat: (message: string, conversation_id?: number | null) =>
    request<any>("/api/agent/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id }),
    }),
  conversation: (id: number) => request<any>(`/api/agent/conversations/${id}`),
  runEvaluation: () => request<any>("/api/evaluation/run", { method: "POST" }),
  latestEvaluation: () => request<any>("/api/evaluation/latest"),
  settings: () => request<any>("/api/settings/status"),
  txn803: () => fetch("/api/demo/txn-803.csv").then((r) => r.text()),
  extractDoc: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<any>("/api/doc-ai/extract", { method: "POST", body: fd });
  },
  confirmDocLedger: (body: Record<string, unknown>) =>
    request<any>("/api/doc-ai/confirm-ledger", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  syntheticPreview: () => request<any>("/api/synthetic/preview?count=10"),
  whatsappThreads: () => request<any>("/api/whatsapp/threads"),
  whatsappThread: (customerId: number) =>
    request<any>(`/api/whatsapp/threads/${customerId}`),
  whatsappSuggestions: () => request<any>("/api/whatsapp/suggested-replies"),
  whatsappSimulateReply: (body: {
    customer_id: number;
    body: string;
    invoice_id?: string;
  }) =>
    request<any>("/api/whatsapp/simulate-reply", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  whatsappUploadEvidence: (customerId: number, file: File, note = "") => {
    const fd = new FormData();
    fd.append("customer_id", String(customerId));
    fd.append("note", note);
    fd.append("file", file);
    return request<any>("/api/whatsapp/upload-evidence", { method: "POST", body: fd });
  },
  whatsappPaymentEvidence: () => request<any>("/api/whatsapp/payment-evidence"),
  voiceCapabilities: () => request<any>("/api/voice/capabilities"),
  voiceCommand: (body: {
    transcript: string;
    language?: string;
    confirmed?: boolean;
    conversation_id?: number | null;
    execute_agent?: boolean;
  }) =>
    request<any>("/api/voice/command", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
