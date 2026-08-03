/**
 * Individual chat message bubble — user (right, indigo) or assistant (left, grey).
 * Assistant bubbles render citations and dataSnapshot when present.
 */

import type { ChatCitation } from "../../services/api";
import { CitationList } from "./CitationCard";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[];
  dataSnapshot?: Record<string, unknown>;
  unavailable?: boolean;
}

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
          isUser
            ? "rounded-br-sm bg-indigo-600 text-white"
            : "rounded-bl-sm bg-gray-100 text-gray-800"
        }`}
      >
        {/* Message text — preserve newlines */}
        <p className="whitespace-pre-wrap">{message.content}</p>

        {/* DataSnapshot: compact key-value list for structured answers */}
        {!isUser && message.dataSnapshot && (
          <DataSnapshotPanel snapshot={message.dataSnapshot} />
        )}

        {/* Citations: expandable source references */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <CitationList citations={message.citations} />
        )}

        {/* Unavailable notice */}
        {!isUser && message.unavailable && (
          <p className="mt-2 text-xs text-amber-600 bg-amber-50 rounded px-2 py-1">
            Document search requires a live Bedrock Knowledge Base.
          </p>
        )}
      </div>
    </div>
  );
}

/* ── DataSnapshot panel ───────────────────────────────────────────────────── */

function DataSnapshotPanel({ snapshot }: { snapshot: Record<string, unknown> }) {
  // Flatten one level deep; skip nested objects (show only scalar values)
  const entries = Object.entries(snapshot).filter(
    ([, v]) => v !== null && v !== undefined && typeof v !== "object"
  );

  // Also render top-level nested "filters" object if present
  const filters = snapshot.filters as Record<string, unknown> | undefined;
  const filterEntries = filters
    ? Object.entries(filters).filter(([, v]) => v !== null && v !== undefined)
    : [];

  if (entries.length === 0 && filterEntries.length === 0) return null;

  return (
    <div className="mt-3 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs">
      <p className="mb-1.5 font-semibold text-gray-500 uppercase tracking-wide text-[10px]">
        Data summary
      </p>
      <dl className="space-y-1">
        {entries.map(([key, value]) => (
          <div key={key} className="flex justify-between gap-4">
            <dt className="text-gray-500 capitalize">{formatKey(key)}</dt>
            <dd className="font-medium text-gray-800 text-right">{formatValue(key, value)}</dd>
          </div>
        ))}
        {filterEntries.map(([key, value]) => (
          <div key={`filter-${key}`} className="flex justify-between gap-4">
            <dt className="text-gray-400 capitalize">Filter: {formatKey(key)}</dt>
            <dd className="text-gray-600 text-right">{String(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function formatKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .toLowerCase()
    .trim();
}

function formatValue(key: string, value: unknown): string {
  if (typeof value === "number") {
    if (key.toLowerCase().includes("amount") || key.toLowerCase().includes("total")) {
      return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return value.toLocaleString("en-US");
  }
  return String(value);
}

/* ── Typing indicator bubble ─────────────────────────────────────────────── */

export function TypingIndicator() {
  return (
    <div className="flex w-full justify-start">
      <div className="rounded-2xl rounded-bl-sm bg-gray-100 px-4 py-3 shadow-sm">
        <span className="flex gap-1 items-center h-4">
          <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.3s]" />
          <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.15s]" />
          <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" />
        </span>
      </div>
    </div>
  );
}
