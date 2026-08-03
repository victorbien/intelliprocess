/**
 * Clickable citation reference card with document name and relevance.
 * Renders nothing when no citations are provided.
 */

import { useState } from "react";
import type { ChatCitation } from "../../services/api";

interface CitationCardProps {
  citation: ChatCitation;
  index: number;
}

export default function CitationCard({ citation, index }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  const relevancePct = Math.round(citation.relevanceScore * 100);

  return (
    <div className="mt-1 rounded border border-indigo-100 bg-indigo-50 text-xs">
      {/* Collapsed header — always visible */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-indigo-100 transition-colors rounded"
      >
        <span className="flex items-center gap-1.5 truncate">
          {/* Document icon */}
          <svg
            className="h-3.5 w-3.5 shrink-0 text-indigo-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <span className="truncate font-medium text-indigo-700">
            [{index + 1}] {citation.documentName}
          </span>
          {citation.pageNumber != null && (
            <span className="shrink-0 text-indigo-400">p.{citation.pageNumber}</span>
          )}
        </span>

        <span className="flex shrink-0 items-center gap-1.5">
          <span className="text-indigo-400">{relevancePct}% match</span>
          {/* Chevron */}
          <svg
            className={`h-3.5 w-3.5 text-indigo-400 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </span>
      </button>

      {/* Expanded snippet */}
      {expanded && (
        <div className="border-t border-indigo-100 px-3 py-2 text-gray-600 leading-relaxed">
          {citation.snippet}
        </div>
      )}
    </div>
  );
}

interface CitationListProps {
  citations: ChatCitation[];
}

/** Renders a labelled list of CitationCards, or nothing when empty. */
export function CitationList({ citations }: CitationListProps) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        Sources
      </p>
      {citations.map((c, i) => (
        <CitationCard key={`${c.documentId}-${i}`} citation={c} index={i} />
      ))}
    </div>
  );
}
