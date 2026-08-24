/**
 * Records Assistant side drawer (Requirement 7).
 *
 * Behaviour implemented:
 *  - Right-anchored drawer, does not navigate away (AC 2).
 *  - Message history, input, send button, loading indicator (AC 3).
 *  - History preserved across close/open within the session (AC 4) — the
 *    component stays mounted; `open` only toggles visibility.
 *  - Send disabled + loading indicator while awaiting a response (AC 5).
 *  - Citations rendered as expandable references (AC 6) via MessageBubble.
 *  - dataSnapshot rendered as a key/value summary (AC 7) via MessageBubble.
 *  - Focus moves to input on open; Escape closes the drawer (AC 8).
 *  - Empty questions are blocked client-side (AC-4.1.4).
 */

import { useEffect, useRef, useState } from "react";

import { chatApi } from "@/services/api";
import { ApiError } from "@/services/types";
import { logger } from "@/services/logger";
import CategoryFilter, { type CategoryOption } from "./CategoryFilter";
import MessageBubble, { TypingIndicator } from "./MessageBubble";
import { clearChat, loadChat, saveChat } from "./storage";
import type { ChatMessage } from "./types";

interface ChatDrawerProps {
  open: boolean;
  onClose: () => void;
}

const MAX_QUESTION_LEN = 1000;

function uid(): string {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

export default function ChatDrawer({ open, onClose }: ChatDrawerProps) {
  // Restore any conversation persisted this browser session (Req 6, Req 7 AC 4).
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadChat().messages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState<CategoryOption>("all");
  const [sessionId, setSessionId] = useState<string | undefined>(() => loadChat().sessionId);

  const inputRef = useRef<HTMLInputElement>(null);
  const listEndRef = useRef<HTMLDivElement>(null);

  // Persist the conversation whenever it changes so it survives reloads.
  useEffect(() => {
    saveChat({ sessionId, messages });
  }, [sessionId, messages]);

  // Focus the input when the drawer opens (AC 8).
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  // Escape closes the drawer (AC 8).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Auto-scroll to the newest message. Guarded because not every environment
  // (e.g. jsdom under tests) implements scrollIntoView.
  useEffect(() => {
    listEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages]);

  const canSend = input.trim().length > 0 && !loading;

  // Start a fresh conversation — clears context and persisted history (AC-4.3.3).
  const startNewConversation = () => {
    setMessages([]);
    setSessionId(undefined);
    setInput("");
    clearChat();
    inputRef.current?.focus();
  };

  const send = async () => {
    const question = input.trim();
    if (!question) return; // AC-4.1.4: no API call for empty input.

    const userMsg: ChatMessage = {
      id: uid(),
      role: "user",
      content: question,
      timestamp: nowIso(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await chatApi.ask(
        question,
        sessionId,
        category === "all" ? undefined : category,
      );
      if (res.sessionId) setSessionId(res.sessionId);

      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          content: res.answer,
          timestamp: nowIso(),
          citations: res.citations,
          sourceType: res.sourceType,
          dataSnapshot: res.dataSnapshot,
        },
      ]);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "The assistant is unavailable right now.";
      logger.error("chat", "Ask failed", err);
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "assistant", content: msg, timestamp: nowIso(), isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-label="Records Assistant"
      aria-hidden={!open}
      className={`fixed inset-y-0 right-0 z-30 flex w-full max-w-md transform flex-col border-l border-slate-200 bg-white shadow-2xl transition-transform duration-300 ${
        open ? "translate-x-0" : "pointer-events-none translate-x-full"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Records Assistant</h2>
          <p className="text-xs text-slate-400">Ask about invoices, policies, and records</p>
        </div>
        <div className="flex items-center gap-2">
          <CategoryFilter value={category} onChange={setCategory} disabled={loading} />
          <button
            type="button"
            onClick={startNewConversation}
            disabled={loading || messages.length === 0}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-50"
          >
            New
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <p className="mt-8 text-center text-sm text-slate-400">
            Ask a question to get started — e.g. “How many invoices are escalated?”
          </p>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
        {loading && <TypingIndicator />}
        <div ref={listEndRef} />
      </div>

      {/* Input */}
      <form
        className="flex items-center gap-2 border-t border-slate-200 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          maxLength={MAX_QUESTION_LEN}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question…"
          className="flex-1 rounded-full border border-slate-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <button
          type="submit"
          disabled={!canSend}
          className="rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
