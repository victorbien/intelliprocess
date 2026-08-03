/**
 * Main chat interface — message list, empty state, text input, send button.
 *
 * Enter sends; Shift+Enter inserts a newline.
 * The input is always editable; the send button is disabled while loading or
 * when the input is empty/blank.
 */

import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "../../services/api";
import MessageBubble, { TypingIndicator, type Message } from "./MessageBubble";

const EXAMPLE_QUESTIONS = [
  "How many invoices are escalated?",
  "Show me Acme invoices",
  "Which invoices exceed $10,000?",
  "What is the status of PO-2024-0456?",
];

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setError(null);
    setInput("");

    // Append user turn immediately
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await sendChatMessage(trimmed, sessionId);

      // Persist sessionId for the whole conversation
      if (!sessionId) setSessionId(response.sessionId);

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        dataSnapshot: response.dataSnapshot,
        unavailable: response.unavailable,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
      // Restore focus to input after response
      textareaRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  }

  const canSend = input.trim().length > 0 && !loading;

  return (
    <div className="flex h-full flex-col">
      {/* ── Message list ──────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 ? (
          <EmptyState onSelect={(q) => handleSend(q)} />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {loading && <TypingIndicator />}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Error banner ───────────────────────────────────────────── */}
      {error && (
        <div className="mx-4 mb-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {/* ── Input area ────────────────────────────────────────────── */}
      <div className="border-t border-gray-200 bg-white px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about invoices, policies, POs…"
            rows={1}
            aria-label="Chat input"
            className="flex-1 resize-none rounded-xl border border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 outline-none transition focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100 max-h-32 leading-relaxed"
            style={{ overflowY: input.includes("\n") ? "auto" : "hidden" }}
          />
          <button
            type="button"
            onClick={() => handleSend(input)}
            disabled={!canSend}
            aria-label="Send message"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow transition hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {/* Send arrow */}
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
              />
            </svg>
          </button>
        </div>
        <p className="mt-1.5 text-[10px] text-gray-400">
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}

/* ── Empty state ─────────────────────────────────────────────────────────── */

function EmptyState({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[280px] px-4 text-center">
      {/* Icon */}
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-100">
        <svg
          className="h-7 w-7 text-indigo-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
          />
        </svg>
      </div>

      <h3 className="mb-1 text-base font-semibold text-gray-800">
        Records Assistant
      </h3>
      <p className="mb-5 text-sm text-gray-500 max-w-xs">
        Ask about invoices, purchase orders, policies, or any organisational records.
      </p>

      {/* Example question chips */}
      <div className="flex flex-col gap-2 w-full max-w-xs">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onSelect(q)}
            className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-left text-sm text-indigo-700 transition hover:bg-indigo-100 hover:border-indigo-300 active:scale-[0.98]"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
