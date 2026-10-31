/** Speech recognition providers — Web Speech now; Saaras-compatible interface for later. */

export type VoiceLanguage = "en-IN" | "hi-IN";

export type TranscriptResult = {
  transcript: string;
  isFinal: boolean;
};

export interface SpeechRecognitionProvider {
  readonly name: string;
  isSupported(): boolean;
  start(opts: {
    language: VoiceLanguage;
    onResult: (r: TranscriptResult) => void;
    onError: (message: string) => void;
    onEnd: () => void;
  }): void;
  stop(): void;
}

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

function getSpeechRecognitionCtor(): (new () => BrowserSpeechRecognition) | null {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export class WebSpeechProvider implements SpeechRecognitionProvider {
  readonly name = "web_speech";
  private rec: BrowserSpeechRecognition | null = null;

  isSupported(): boolean {
    return typeof window !== "undefined" && !!getSpeechRecognitionCtor();
  }

  start(opts: {
    language: VoiceLanguage;
    onResult: (r: TranscriptResult) => void;
    onError: (message: string) => void;
    onEnd: () => void;
  }): void {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      opts.onError("Speech recognition is not supported in this browser. Use Chrome/Edge, or type below.");
      return;
    }
    this.stop();
    const rec = new Ctor();
    this.rec = rec;
    rec.lang = opts.language;
    rec.continuous = false;
    rec.interimResults = true;
    rec.onresult = (event: any) => {
      let interim = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0].transcript as string;
        if (event.results[i].isFinal) finalText += piece;
        else interim += piece;
      }
      if (finalText) opts.onResult({ transcript: finalText.trim(), isFinal: true });
      else if (interim) opts.onResult({ transcript: interim.trim(), isFinal: false });
    };
    rec.onerror = (event: any) => {
      const code = event?.error || "unknown";
      if (code === "not-allowed" || code === "service-not-allowed") {
        opts.onError("Microphone permission denied. Allow mic access or use text fallback.");
      } else if (code === "no-speech") {
        opts.onError("No speech detected. Try again or type your command.");
      } else {
        opts.onError(`Speech error: ${code}`);
      }
    };
    rec.onend = () => opts.onEnd();
    try {
      rec.start();
    } catch {
      opts.onError("Could not start microphone. Check browser permissions.");
    }
  }

  stop(): void {
    if (!this.rec) return;
    try {
      this.rec.onresult = null;
      this.rec.onerror = null;
      this.rec.onend = null;
      this.rec.stop();
    } catch {
      /* ignore */
    }
    this.rec = null;
  }
}

/** Future: upload audio to /api/voice/transcribe (Sarvam Saaras). Not active in this build. */
export class SarvamSaarasClientProvider implements SpeechRecognitionProvider {
  readonly name = "sarvam_saaras_v4";

  isSupported(): boolean {
    return false;
  }

  start(): void {
    throw new Error("Saaras client STT not enabled — use WebSpeechProvider");
  }

  stop(): void {}
}

export function createDefaultSpeechProvider(): SpeechRecognitionProvider {
  return new WebSpeechProvider();
}
