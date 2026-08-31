/**
 * Main chat interface — message list, empty state, text input, send button.
 *
 * Enter sends; Shift+Enter inserts a newline.
 * The input is always editable; the send button is disabled while loading or
 * when the input is empty/blank.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  streamChatMessage,
  summarizeSession,
  getLatestSessionSummary,
} from "../../services/api";
import MessageBubble, { TypingIndicator, type Message } from "./MessageBubble";
import SummaryCard from "./SummaryCard";

interface PresetQuestionGroup {
  group: string;
  questions: string[];
}

// Curated demo questions covering every verified capability (structured data
// queries, supplier analytics, and Knowledge Base document search). Clicking a
// chip sends the exact text, so a presenter never has to type during a demo.
const PRESET_QUESTION_GROUPS: PresetQuestionGroup[] = [
  {
    group: "📄 Invoices",
    questions: [
      "How many invoices are there in each status?",
      "How many invoices are escalated?",
      "Which invoices exceed $10,000?",
      "Show me invoices from Acme Office Supplies",
    ],
  },
  {
    group: "🏭 Suppliers",
    questions: [
      "Who are our top suppliers by spend?",
      "Which suppliers have the best order accuracy?",
      "Which suppliers have the lowest prices?",
    ],
  },
  {
    group: "📁 Policies & Documents",
    questions: [
      "What is our corporate travel meal allowance?",
      "What are the auto-approval rules for invoices?",
      "What volume discounts does the Acme supply agreement offer?",
    ],
  },
];

// Exact resume-prompt text required by the spec (Req 7.1).
const RESUME_PROMPT = "Hello! Do you want to continue the last conversation?";

interface ChatWindowProps {
  // Drawer visibility, threaded down from App.tsx via ChatDrawer. ChatWindow
  // stays mounted while the drawer only slides via CSS transform, so this prop
  // is how we detect a real "close" and run the close-time cleanup.
  open: boolean;
}

export default function ChatWindow({ open }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  // Controls the always-available "Suggested questions" panel above the input.
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Resume experience: the most recent session's stored summary, if any.
  const [resumeSummary, setResumeSummary] = useState<
    { sessionId: string; summary: string } | null
  >(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Latest sessionId + message count held in refs so the cleanup can read
  // current values without re-registering the effect (Req 6.1, 6.4).
  const sessionIdRef = useRef<string | undefined>(undefined);
  const messageCountRef = useRef(0);

  // Previous value of `open`, so the open-driven effect can detect true→false
  // (drawer close) and false→true (drawer open) transitions.
  const prevOpenRef = useRef(open);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    messageCountRef.current = messages.length;
  }, [messages]);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, loading]);

  // Fetch the latest session summary to offer a resume prompt. Extracted so it
  // can run both on the initial open and whenever the drawer is re-opened.
  const refreshResumeSummary = useCallback(() => {
    let cancelled = false;
    getLatestSessionSummary()
      .then((session) => {
        if (cancelled) return;
        if (session && session.summary) {
          setResumeSummary({ sessionId: session.sessionId, summary: session.summary });
        }
      })
      .catch(() => {
        // Failure to load a prior summary simply suppresses the resume prompt.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // On the initial render, if the drawer is already open, fetch the resume
  // summary once (mirrors the original mount-time behavior).
  useEffect(() => {
    if (open) {
      return refreshResumeSummary();
    }
    // Only meant to run for the initial mount decision.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Drawer open/close transitions. Because ChatWindow never unmounts on close,
  // this effect performs the close-time cleanup (abort + summary + loading
  // reset) and refreshes the resume prompt on re-open.
  useEffect(() => {
    const prevOpen = prevOpenRef.current;
    prevOpenRef.current = open;

    // Close transition: abort any in-flight stream, reset loading so the send
    // button is usable next time, and fire the fire-and-forget summary when a
    // session with messages exists.
    if (prevOpen && !open) {
      abortRef.current?.abort();
      setLoading(false);
      if (sessionIdRef.current && messageCountRef.current > 0) {
        summarizeSession(sessionIdRef.current);
      }
    }

    // Open transition: refresh the resume prompt so re-opening reflects any
    // summary stored since the last open.
    if (!prevOpen && open) {
      return refreshResumeSummary();
    }
  }, [open, refreshResumeSummary]);

  // On full page unmount: abort any in-flight stream, and fire a
  // fire-and-forget summary request when a session with messages exists.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (sessionIdRef.current && messageCountRef.current > 0) {
        summarizeSession(sessionIdRef.current);
      }
    };
  }, []);

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

    // Append an empty assistant message so the typewriter effect can start
    // rendering tokens as they arrive.
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);
    setLoading(true);

    // New AbortController per send; stored so unmount can cancel the stream.
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const event of streamChatMessage(
        trimmed,
        sessionId,
        undefined,
        controller.signal
      )) {
        if (event.type === "token") {
          // Typewriter: append the incoming fragment to the assistant message
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + event.content } : m
            )
          );
        } else if (event.type === "done") {
          // Persist sessionId for the whole conversation
          if (!sessionId) setSessionId(event.sessionId);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    citations: event.citations,
                    dataSnapshot: event.dataSnapshot ?? undefined,
                  }
                : m
            )
          );
        } else if (event.type === "error") {
          setError(event.message);
        }
        // "ping" keep-alive events are ignored.
      }
    } catch (err) {
      // AbortError is expected when the drawer closes mid-stream — swallow it.
      if ((err as Error).name !== "AbortError") {
        setError(
          err instanceof Error ? err.message : "Something went wrong. Please try again."
        );
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
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
          <>
            {resumeSummary && (
              <div className="mb-4 space-y-3">
                <p className="text-sm font-medium text-gray-700">{RESUME_PROMPT}</p>
                <SummaryCard
                  sessionId={resumeSummary.sessionId}
                  summary={resumeSummary.summary}
                />
              </div>
            )}
            <EmptyState onSelect={(q) => handleSend(q)} />
          </>
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

      {/* ── Suggested questions toggle (always available) ─────────── */}
      <div className="px-4">
        <button
          type="button"
          onClick={() => setShowSuggestions((v) => !v)}
          aria-expanded={showSuggestions}
          aria-controls="suggested-questions-panel"
          className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs font-medium text-gray-500 transition hover:bg-gray-50 hover:text-gray-700"
        >
          <span>Suggested questions</span>
          <svg
            className={`h-4 w-4 transition-transform ${showSuggestions ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
          </svg>
        </button>

        {showSuggestions && (
          <div id="suggested-questions-panel" className="pb-2 pt-1">
            <PresetQuestionGroups
              onSelect={(q) => {
                setShowSuggestions(false);
                handleSend(q);
              }}
            />
          </div>
        )}
      </div>

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

      {/* Grouped preset question chips */}
      <div className="w-full max-w-xs">
        <PresetQuestionGroups onSelect={onSelect} />
      </div>
    </div>
  );
}

/* ── Grouped preset question chips ───────────────────────────────────────── */

// Single source of truth for rendering the grouped preset questions. Reused by
// both the empty state and the always-available "Suggested questions" toggle so
// the question strings are never duplicated.
function PresetQuestionGroups({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex flex-col gap-4">
      {PRESET_QUESTION_GROUPS.map((group) => (
        <div key={group.group} className="flex flex-col gap-2">
          <h4 className="text-left text-xs font-semibold uppercase tracking-wide text-gray-400">
            {group.group}
          </h4>
          {group.questions.map((q) => (
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
      ))}
    </div>
  );
}
