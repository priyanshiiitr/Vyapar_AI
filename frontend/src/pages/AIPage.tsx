import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Loader2, MessageSquarePlus, Trash2, Wrench } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import {
  createConversation,
  deleteConversation,
  getActiveConversationId,
  getConversation,
  listConversations,
  setActiveConversationId,
  titleFromMessage,
  upsertConversation,
  type ChatItem,
  type StoredConversation,
} from "@/lib/aiConversationStore";

const SUGGESTIONS = [
  "Analyze my outstanding payments.",
  "Show me overdue invoices.",
  "Prepare a Hinglish reminder for invoice R-104.",
  "Give me invoice R-104 details.",
  "Record ABC Stores payment promise for Friday.",
  "Explain unmatched transactions.",
];

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function AIPage() {
  const [history, setHistory] = useState<StoredConversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [items, setItems] = useState<ChatItem[]>([]);
  const [serverConversationId, setServerConversationId] = useState<number | null>(null);

  const active = useMemo(
    () => history.find((c) => c.id === activeId) ?? null,
    [history, activeId],
  );

  function refreshHistory(preferId?: string | null) {
    const rows = listConversations();
    setHistory(rows);
    const nextId =
      preferId ??
      getActiveConversationId() ??
      rows[0]?.id ??
      null;
    if (!nextId) {
      const created = createConversation();
      setHistory(listConversations());
      setActiveId(created.id);
      setItems([]);
      setServerConversationId(null);
      return;
    }
    setActiveId(nextId);
    setActiveConversationId(nextId);
    const conv = getConversation(nextId);
    setItems(conv?.items ?? []);
    setServerConversationId(conv?.serverConversationId ?? null);
  }

  useEffect(() => {
    refreshHistory();
  }, []);

  function selectConversation(id: string) {
    const conv = getConversation(id);
    if (!conv) return;
    setActiveId(id);
    setActiveConversationId(id);
    setItems(conv.items);
    setServerConversationId(conv.serverConversationId);
  }

  function startNewChat() {
    const created = createConversation();
    setHistory(listConversations());
    setActiveId(created.id);
    setItems([]);
    setServerConversationId(null);
    setInput("");
  }

  function removeConversation(id: string) {
    deleteConversation(id);
    const remaining = listConversations();
    if (!remaining.length) {
      startNewChat();
      return;
    }
    setHistory(remaining);
    const next = remaining[0];
    setActiveId(next.id);
    setActiveConversationId(next.id);
    setItems(next.items);
    setServerConversationId(next.serverConversationId);
  }

  function persist(nextItems: ChatItem[], serverId: number | null, firstUserMessage?: string) {
    if (!activeId) return;
    const existing = getConversation(activeId);
    const title =
      existing?.title && existing.title !== "New chat"
        ? existing.title
        : titleFromMessage(firstUserMessage || existing?.title || "New chat");
    const saved = upsertConversation({
      id: activeId,
      title,
      createdAt: existing?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      serverConversationId: serverId,
      items: nextItems,
    });
    setHistory(listConversations());
    setItems(saved.items);
    setServerConversationId(saved.serverConversationId);
  }

  const chat = useMutation({
    mutationFn: (message: string) => api.chat(message, serverConversationId),
    onSuccess: (res, message) => {
      const sid = (res.conversation_id as number | undefined) ?? serverConversationId;
      if (sid) setServerConversationId(sid);
      const turn: ChatItem[] = [{ kind: "user", text: message }];
      if (res.tool_calls?.length) turn.push({ kind: "tools", tools: res.tool_calls });
      turn.push({
        kind: "assistant",
        text: res.assistant_message || res.error || "No response",
      });
      setItems((prev) => {
        const merged = [...prev, ...turn];
        persist(merged, sid ?? null, message);
        return merged;
      });
      if (!res.ok) toast.error(res.error || "AI error");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function send(message: string) {
    if (!message.trim() || chat.isPending) return;
    if (!activeId) startNewChat();
    setInput("");
    chat.mutate(message.trim());
  }

  return (
    <div className="space-y-4 animate-rise">
      <div>
        <h2 className="font-display text-4xl">AI Teammate</h2>
        <p className="text-[var(--muted)]">
          Sarvam-105b selects tools. Chat history stays in this browser (local storage).
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="flex max-h-[720px] flex-col p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <CardTitle className="!mt-0">History</CardTitle>
            <Button type="button" size="sm" variant="ghost" onClick={startNewChat}>
              <MessageSquarePlus size={16} />
              New
            </Button>
          </div>

          <div className="min-h-0 flex-1 space-y-2 overflow-auto pr-1">
            {!history.length && (
              <p className="px-1 text-sm text-[var(--muted)]">No saved chats yet.</p>
            )}
            {history.map((conv) => {
              const selected = conv.id === activeId;
              return (
                <div
                  key={conv.id}
                  className={`group rounded-xl border px-3 py-2 transition ${
                    selected
                      ? "border-teal-700/40 bg-teal-800 text-white"
                      : "border-[var(--line)] bg-white/70 hover:bg-white"
                  }`}
                >
                  <button
                    type="button"
                    className="w-full text-left"
                    onClick={() => selectConversation(conv.id)}
                  >
                    <div className="line-clamp-2 text-sm font-medium leading-snug">
                      {conv.title}
                    </div>
                    <div
                      className={`mt-1 text-xs ${
                        selected ? "text-white/70" : "text-[var(--muted)]"
                      }`}
                    >
                      {formatWhen(conv.updatedAt)}
                      {conv.items.length
                        ? ` · ${conv.items.filter((i) => i.kind === "user").length} msgs`
                        : ""}
                    </div>
                  </button>
                  <div className="mt-1 flex justify-end opacity-0 transition group-hover:opacity-100">
                    <button
                      type="button"
                      className={`rounded-lg p-1 ${
                        selected
                          ? "text-white/80 hover:bg-white/10"
                          : "text-[var(--muted)] hover:bg-black/5"
                      }`}
                      aria-label="Delete conversation"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeConversation(conv.id);
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 border-t border-[var(--line)] pt-3">
            <CardTitle>Suggestions</CardTitle>
            <div className="mt-2 flex flex-col gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="rounded-lg border border-[var(--line)] bg-white/70 px-2.5 py-1.5 text-left text-xs hover:bg-white"
                  onClick={() => send(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </Card>

        <Card className="flex min-h-[520px] max-h-[720px] flex-col">
          <div className="mb-3 flex items-center justify-between gap-3 border-b border-[var(--line)] pb-3">
            <div>
              <div className="font-medium">{active?.title || "New chat"}</div>
              <div className="text-xs text-[var(--muted)]">
                {serverConversationId
                  ? `Server thread #${serverConversationId}`
                  : "Saved locally in this browser"}
              </div>
            </div>
            <Button type="button" size="sm" variant="ghost" onClick={startNewChat}>
              New chat
            </Button>
          </div>

          <div className="min-h-0 flex-1 space-y-3 overflow-auto">
            {!items.length && (
              <div className="flex h-full flex-col items-center justify-center gap-3 py-16 text-center text-[var(--muted)]">
                <Bot size={36} className="text-teal-700" />
                <p>Ask about receivables, overdue invoices, reminders, or promises.</p>
              </div>
            )}
            {items.map((item, idx) => {
              if (item.kind === "user") {
                return (
                  <div
                    key={idx}
                    className="ml-auto max-w-[85%] rounded-2xl bg-teal-800 px-4 py-3 text-sm text-white"
                  >
                    {item.text}
                  </div>
                );
              }
              if (item.kind === "tools") {
                return (
                  <div key={idx} className="space-y-2">
                    {item.tools.map((t) => (
                      <div
                        key={t.id}
                        className="rounded-xl border border-[var(--line)] bg-white/70 px-3 py-2 text-sm"
                      >
                        <div className="flex items-center gap-2 font-semibold">
                          <Wrench size={14} /> {t.name}
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">
                            {t.status}
                          </span>
                        </div>
                        <pre className="mt-2 max-h-40 overflow-auto text-xs text-[var(--muted)]">
                          {JSON.stringify(t.result, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                );
              }
              return (
                <div
                  key={idx}
                  className="max-w-[90%] whitespace-pre-wrap rounded-2xl bg-black/[0.04] px-4 py-3 text-sm"
                >
                  {item.text}
                </div>
              );
            })}
            {chat.isPending && (
              <div className="inline-flex items-center gap-2 text-sm text-[var(--muted)]">
                <Loader2 className="animate-spin" size={16} /> Working with tools…
              </div>
            )}
          </div>

          <div className="mt-4 flex gap-2">
            <input
              className="h-11 flex-1 rounded-xl border border-[var(--line)] bg-white px-3 text-sm"
              value={input}
              placeholder="Message Vyapar AI…"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
            />
            <Button onClick={() => send(input)} disabled={chat.isPending}>
              Send
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
