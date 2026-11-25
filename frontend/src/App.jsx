import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const newSessionId = () => "s-" + Math.random().toString(36).slice(2, 10);

function errorText(status, detail) {
  if (status === 503) return "All API keys are unavailable right now. Try again in a moment.";
  if (status === 422) return "Check your message. It must be 1 to 4000 characters.";
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  return detail ? String(detail) : `Request failed (${status}).`;
}

export default function App() {
  const [sessionId] = useState(newSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);

    const body = { session_id: sessionId, message: text };
    if (systemPrompt.trim()) body.system_prompt = systemPrompt.trim();

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw Object.assign(new Error(errorText(res.status, data.detail)), { status: res.status });
      setMessages((m) => [...m, { role: "assistant", content: data.reply, meta: data.metadata }]);
    } catch (err) {
      const text = err.status ? err.message : "Can't reach the server. Check your connection and try again.";
      setMessages((m) => [...m, { role: "error", content: text }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="top">
        <h1>Chat</h1>
        <span className="session">{sessionId}</span>
      </header>

      <details className="system">
        <summary>System prompt</summary>
        <textarea
          data-testid="system-prompt-input"
          placeholder="Optional. Sets the assistant's behaviour for this session."
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          rows={3}
        />
      </details>

      <section className="log" aria-live="polite">
        {messages.length === 0 && <p className="empty">Ask a question to start the conversation.</p>}
        {messages.map((m, i) => {
          if (m.role === "user") return <p key={i} className="bubble user">{m.content}</p>;
          if (m.role === "error") return <p key={i} className="error" role="alert">{m.content}</p>;
          const meta = m.meta;
          return (
            <article key={i} className="reply" data-testid="assistant-message">
              <p className="text">{m.content}</p>
              <dl className="meta">
                <div><dt>Source</dt><dd data-testid="meta-source">{meta.resolution_source}</dd></div>
                <div><dt>Model</dt><dd data-testid="meta-model">{meta.model}</dd></div>
                <div><dt>Latency</dt><dd data-testid="meta-latency">{meta.latency_ms} ms</dd></div>
                <div><dt>Input tokens</dt><dd data-testid="meta-input-tokens">{meta.input_tokens}</dd></div>
                <div><dt>Output tokens</dt><dd data-testid="meta-output-tokens">{meta.output_tokens}</dd></div>
              </dl>
            </article>
          );
        })}
        <div ref={endRef} />
      </section>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <textarea
          data-testid="chat-input"
          aria-label="Message"
          value={input}
          rows={2}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button data-testid="send-button" type="submit" disabled={busy || !input.trim()}>
          {busy ? "Sending" : "Send"}
        </button>
      </form>
    </main>
  );
}
