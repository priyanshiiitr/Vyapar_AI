export type ToolCall = {
  id: string;
  name: string;
  arguments: string;
  status: string;
  result: unknown;
};

export type ChatItem =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "tools"; tools: ToolCall[] };

export type StoredConversation = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  serverConversationId: number | null;
  items: ChatItem[];
};

const STORAGE_KEY = "vyapar.ai.conversations.v1";
const ACTIVE_KEY = "vyapar.ai.activeConversationId.v1";

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readAll(): StoredConversation[] {
  if (!canUseStorage()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredConversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(conversations: StoredConversation[]) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

export function listConversations(): StoredConversation[] {
  return readAll().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getActiveConversationId(): string | null {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(ACTIVE_KEY);
}

export function setActiveConversationId(id: string | null) {
  if (!canUseStorage()) return;
  if (!id) window.localStorage.removeItem(ACTIVE_KEY);
  else window.localStorage.setItem(ACTIVE_KEY, id);
}

export function getConversation(id: string): StoredConversation | null {
  return readAll().find((c) => c.id === id) ?? null;
}

export function createConversation(title = "New chat"): StoredConversation {
  const now = new Date().toISOString();
  const conv: StoredConversation = {
    id: crypto.randomUUID(),
    title,
    createdAt: now,
    updatedAt: now,
    serverConversationId: null,
    items: [],
  };
  const all = readAll();
  all.unshift(conv);
  writeAll(all);
  setActiveConversationId(conv.id);
  return conv;
}

export function upsertConversation(conv: StoredConversation) {
  const all = readAll();
  const idx = all.findIndex((c) => c.id === conv.id);
  const next = { ...conv, updatedAt: new Date().toISOString() };
  if (idx >= 0) all[idx] = next;
  else all.unshift(next);
  writeAll(all);
  return next;
}

export function deleteConversation(id: string) {
  writeAll(readAll().filter((c) => c.id !== id));
  if (getActiveConversationId() === id) setActiveConversationId(null);
}

export function titleFromMessage(message: string): string {
  const cleaned = message.replace(/\s+/g, " ").trim();
  if (!cleaned) return "New chat";
  return cleaned.length > 48 ? `${cleaned.slice(0, 48)}…` : cleaned;
}
