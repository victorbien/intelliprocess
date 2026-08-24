/**
 * A single chat message bubble (Requirement 7 AC 3, 6, 7).
 *
 * Assistant messages may include citations (expandable) and a dataSnapshot
 * (key/value summary). User messages are right-aligned.
 */

import CitationCard from "./CitationCard";
import DataSnapshot from "./DataSnapshot";
import Markdown from "./Markdown";
import type { ChatMessage } from "./types";

/** Animated "assistant is typing" indicator. */
export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl bg-slate-100 px-3 py-2 text-sm text-slate-500">
        <span className="inline-flex gap-1">
          <span className="animate-bounce">•</span>
          <span className="animate-bounce [animation-delay:150ms]">•</span>
          <span className="animate-bounce [animation-delay:300ms]">•</span>
        </span>
      </div>
    </div>
  );
}

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
          isUser
            ? "bg-indigo-600 text-white"
            : message.isError
              ? "bg-red-50 text-red-700"
              : "bg-slate-100 text-slate-800"
        }`}
      >
        {isUser || message.isError ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : (
          // Assistant answers support markdown rendering (AC-4.1.3).
          <Markdown content={message.content} />
        )}

        {message.dataSnapshot && Object.keys(message.dataSnapshot).length > 0 && (
          <DataSnapshot snapshot={message.dataSnapshot} />
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-[10px] font-semibold uppercase text-slate-400">Sources</p>
            {message.citations.map((c, i) => (
              <CitationCard key={`${c.documentId}-${i}`} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
