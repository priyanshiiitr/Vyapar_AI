import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Mic, MicOff, Square, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { createDefaultSpeechProvider, type VoiceLanguage } from "@/voice/providers";

type Phase = "idle" | "listening" | "review" | "processing" | "done" | "error";

const EXAMPLES = [
  "Show overdue invoices",
  "Open collections",
  "Show total outstanding",
  "Pending approvals dikhao",
  "Prepare a Hinglish reminder for invoice R-104",
];

export function VoiceDock() {
  const navigate = useNavigate();
  const provider = useMemo(() => createDefaultSpeechProvider(), []);
  const supported = provider.isSupported();

  const [open, setOpen] = useState(false);
  const [language, setLanguage] = useState<VoiceLanguage>("en-IN");
  const [phase, setPhase] = useState<Phase>("idle");
  const [live, setLive] = useState("");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<string | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{
    message: string;
    reason: string;
  } | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [toolNames, setToolNames] = useState<string[]>([]);

  useEffect(() => {
    return () => provider.stop();
  }, [provider]);

  function resetPanel() {
    provider.stop();
    setPhase("idle");
    setLive("");
    setTranscript("");
    setError(null);
    setResponse(null);
    setPendingConfirm(null);
    setToolNames([]);
  }

  function startListening() {
    if (!supported) {
      setError("Speech recognition unsupported. Type your command below.");
      setPhase("review");
      return;
    }
    setError(null);
    setResponse(null);
    setPendingConfirm(null);
    setLive("");
    setTranscript("");
    setToolNames([]);
    setPhase("listening");
    provider.start({
      language,
      onResult: ({ transcript: t, isFinal }) => {
        if (isFinal) {
          setTranscript((prev) => (prev ? `${prev} ${t}` : t).trim());
          setLive("");
        } else {
          setLive(t);
        }
      },
      onError: (message) => {
        setError(message);
        setPhase("error");
        provider.stop();
      },
      onEnd: () => {
        setPhase((p) => (p === "listening" ? "review" : p));
      },
    });
  }

  function stopListening() {
    provider.stop();
    setPhase("review");
  }

  async function runCommand(text: string, confirmed = false) {
    const cleaned = text.trim();
    if (!cleaned) {
      setError("Add a transcript before running.");
      setPhase("error");
      return;
    }
    setPhase("processing");
    setError(null);
    setResponse(null);
    setPendingConfirm(null);
    try {
      const res = await api.voiceCommand({
        transcript: cleaned,
        language,
        confirmed,
        conversation_id: conversationId,
        execute_agent: true,
      });

      if (!res.ok) {
        setError(res.error || "Voice command failed");
        setPhase("error");
        return;
      }

      if (res.action === "navigate" && res.route) {
        navigate(res.route);
        setResponse(`Opened ${res.label || res.route}`);
        setPhase("done");
        toast.success(`Navigated to ${res.label || res.route}`);
        return;
      }

      if (res.action === "needs_confirmation") {
        setPendingConfirm({
          message: res.agent_message || cleaned,
          reason: res.confirm_reason || "Confirm before continuing.",
        });
        setTranscript(res.agent_message || cleaned);
        setPhase("review");
        return;
      }

      if (res.action === "agent_query") {
        if (res.conversation_id) setConversationId(res.conversation_id);
        const tools = (res.tool_calls || []).map((t: any) => t.name).filter(Boolean);
        setToolNames(tools);
        setResponse(res.assistant_message || "Done.");
        setPhase("done");
        if (res.agent && res.agent.ok === false) {
          toast.error(res.assistant_message || "Agent error");
        } else {
          toast.success("Voice command processed");
        }
        return;
      }

      setError("Unsupported voice action");
      setPhase("error");
    } catch (e: any) {
      setError(e.message || "Request failed");
      setPhase("error");
    }
  }

  const displayText = transcript || live;

  return (
    <>
      <button
        type="button"
        aria-label="Voice browse Vyapar AI"
        onClick={() => {
          setOpen(true);
          if (!transcript && phase === "idle") {
            /* panel opens idle so user picks language */
          }
        }}
        className={cn(
          "fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full",
          "bg-[var(--teal)] text-white shadow-[0_12px_40px_rgba(15,118,110,0.45)]",
          "transition hover:bg-[var(--teal-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
        )}
      >
        <Mic size={22} />
      </button>

      {open && (
        <div className="fixed inset-x-3 bottom-24 z-40 mx-auto w-full max-w-md animate-rise sm:inset-x-auto sm:right-6">
          <div className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[#f7faf8]/95 shadow-[0_20px_60px_rgba(20,35,28,0.25)] backdrop-blur">
            <div className="flex items-center justify-between border-b border-[var(--line)] bg-[#10251f] px-4 py-3 text-teal-50">
              <div>
                <p className="text-sm font-semibold">Voice browse</p>
                <p className="text-xs text-teal-100/70">EN / Hindi · allowlisted navigation · existing AI teammate</p>
              </div>
              <button type="button" className="rounded-lg p-1 hover:bg-white/10" onClick={() => { resetPanel(); setOpen(false); }}>
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 p-4">
              <div className="flex gap-2">
                {(
                  [
                    ["en-IN", "English"],
                    ["hi-IN", "Hindi"],
                  ] as const
                ).map(([code, label]) => (
                  <button
                    key={code}
                    type="button"
                    onClick={() => setLanguage(code)}
                    className={cn(
                      "rounded-xl border px-3 py-1.5 text-xs font-semibold",
                      language === code
                        ? "border-teal-700 bg-teal-50 text-teal-900"
                        : "border-[var(--line)] bg-white text-[var(--muted)]"
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {!supported && (
                <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  Web Speech API not available in this browser. Use the text box (Chrome/Edge recommended).
                </p>
              )}

              <div
                className={cn(
                  "min-h-[72px] rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm",
                  phase === "listening" && "ring-2 ring-teal-500/40"
                )}
              >
                {phase === "listening" && (
                  <p className="mb-1 flex items-center gap-2 text-xs font-semibold text-teal-800">
                    <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-red-500" /> Listening…
                  </p>
                )}
                {phase === "processing" && (
                  <p className="mb-1 flex items-center gap-2 text-xs font-semibold text-[var(--muted)]">
                    <Loader2 size={12} className="animate-spin" /> Processing with Vyapar AI…
                  </p>
                )}
                <textarea
                  className="min-h-[56px] w-full resize-none bg-transparent outline-none"
                  placeholder={supported ? "Tap mic, speak, then edit if needed…" : "Type a command…"}
                  value={phase === "listening" && live && !transcript ? live : transcript}
                  onChange={(e) => {
                    setTranscript(e.target.value);
                    if (phase !== "listening") setPhase("review");
                  }}
                  disabled={phase === "processing"}
                />
              </div>

              {pendingConfirm && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
                  <p className="font-semibold">Merchant confirmation required</p>
                  <p className="mt-1">{pendingConfirm.reason}</p>
                  <div className="mt-2 flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => runCommand(pendingConfirm.message, true)}
                    >
                      Confirm & run
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setPendingConfirm(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {error && (
                <p className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-800">{error}</p>
              )}

              {response && (
                <div className="rounded-xl bg-black/[0.04] px-3 py-2 text-sm whitespace-pre-wrap">
                  {response}
                  {!!toolNames.length && (
                    <p className="mt-2 text-xs text-[var(--muted)]">Tools: {toolNames.join(", ")}</p>
                  )}
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                {phase === "listening" ? (
                  <Button variant="secondary" onClick={stopListening}>
                    <Square size={14} /> Stop
                  </Button>
                ) : (
                  <Button onClick={startListening} disabled={phase === "processing" || !supported}>
                    {supported ? <Mic size={14} /> : <MicOff size={14} />}
                    {supported ? "Listen" : "Mic unavailable"}
                  </Button>
                )}
                <Button
                  variant="secondary"
                  disabled={phase === "processing" || !(transcript || displayText).trim() || !!pendingConfirm}
                  onClick={() => runCommand(transcript || displayText, false)}
                >
                  Run command
                </Button>
                <Button variant="ghost" size="sm" onClick={resetPanel}>
                  Clear
                </Button>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    className="rounded-full border border-[var(--line)] bg-white px-2.5 py-1 text-[11px] text-[var(--muted)] hover:text-[var(--ink)]"
                    onClick={() => {
                      setTranscript(ex);
                      setPhase("review");
                    }}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
