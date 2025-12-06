import { useState } from "react";

type Props = {
  onSend: (prompt: string) => void;
  loading: boolean;
  messages: { role: "user" | "assistant"; content: string }[];
};

export function ChatPanel({ onSend, loading, messages }: Props) {
  const [input, setInput] = useState("");
  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  };
  return (
    <div className="chat-panel">
      <div className="chat-header">Chat</div>
      <div className="chat-history">
        {messages.length === 0 && <div className="hint">No messages yet.</div>}
        {messages.map((m, idx) => (
          <div key={idx} className={`chat-bubble ${m.role}`}>
            <div className="chat-role">{m.role === "user" ? "You" : "Assistant"}</div>
            <pre className="chat-content">{m.content}</pre>
          </div>
        ))}
      </div>
      <textarea
        placeholder="Ask anything (e.g., revenue by channel, cohort performance)..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />
      <button className="btn" onClick={handleSend} disabled={loading}>
        {loading ? "Thinking..." : "Send"}
      </button>
      <p className="hint">Responses update the dashboard dynamically.</p>
    </div>
  );
}
