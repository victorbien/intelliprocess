/**
 * Summary card shown at the top of the chat when a stored conversation
 * summary exists for the user's last session.
 *
 * By default it displays the summary text with the full message history
 * collapsed. Activating the "view full history" expander lazily loads the
 * session's turns via `getSession` and renders them as MessageBubbles beneath
 * the summary. A load failure shows an inline error while keeping the summary
 * visible.
 */

import { useState } from "react";
import { getSession, type ChatMessageItem } from "../../services/api";
import MessageBubble, { type Message } from "./MessageBubble";

interface SummaryCardProps {
  sessionId: string;
  summary: string;
}

// Map a persisted ChatMessageItem to the shape MessageBubble expects.
function toMessage(item: ChatMessageItem, index: number): Message {
  const role = item.role === "assistant" ? "assistant" : "user";
  return {
    id: `history-${index}`,
    role,
    content: item.content,
    citations: item.citations ?? undefined,
  };
}

export default function SummaryCard({ sessionId, summary }: SummaryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Message[] | null>(null);

  async function handleToggle() {
    // Collapse if already expanded.
    if (expanded) {
      setExpanded(false);
      return;
    }

    setExpanded(true);

    // Lazily load the history only once.
    if (history !== null || loading) return;

    setLoading(true);
    setError(null);
    try {
      const detail = await getSession(sessionId);
      setHistory(detail.messages.map(toMessage));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load the full conversation history."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-indigo-500">
        Conversation summary
      </p>

      {/* Summary text — always visible */}
      <p className="whitespace-pre-wrap text-gray-700">{summary}</p>

      {/* Expander toggle */}
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={expanded}
        className="mt-2 text-xs font-medium text-indigo-600 transition hover:text-indigo-800"
      >
        {expanded ? "Hide full history" : "View full history"}
      </button>

      {/* Expanded history region */}
      {expanded && (
        <div className="mt-3 space-y-3 border-t border-indigo-200 pt-3">
          {loading && <p className="text-xs text-gray-500">Loading history…</p>}

          {error && (
            <p className="rounded bg-red-50 px-2 py-1 text-xs text-red-700 border border-red-200">
              {error}
            </p>
          )}

          {!loading &&
            !error &&
            history &&
            history.map((msg) => <MessageBubble key={msg.id} message={msg} />)}
        </div>
      )}
    </div>
  );
}
