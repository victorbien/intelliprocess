/**
 * Individual chat message bubble — user (right, indigo) or assistant (left, grey).
 * Assistant bubbles render citations and dataSnapshot when present.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
        {/* Message text — user is plain; assistant renders Markdown */}
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <MarkdownContent content={message.content} />
        )}

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

/* ── Markdown renderer for assistant messages ─────────────────────────────── */

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="text-sm leading-relaxed [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-1.5">{children}</p>,
          ul: ({ children }) => (
            <ul className="my-1.5 list-disc space-y-0.5 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-1.5 list-decimal space-y-0.5 pl-5">{children}</ol>
          ),
          li: ({ children }) => <li className="marker:text-gray-400">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">{children}</strong>
          ),
          h1: ({ children }) => <h4 className="mb-1 mt-2 font-semibold">{children}</h4>,
          h2: ({ children }) => <h4 className="mb-1 mt-2 font-semibold">{children}</h4>,
          h3: ({ children }) => <h4 className="mb-1 mt-2 font-semibold">{children}</h4>,
          code: ({ children }) => (
            <code className="rounded bg-gray-200 px-1 py-0.5 text-[12px] text-gray-800">
              {children}
            </code>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-indigo-600 underline"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-200/60">{children}</thead>,
          th: ({ children }) => (
            <th className="border border-gray-300 px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-gray-300 px-2 py-1">{children}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
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
