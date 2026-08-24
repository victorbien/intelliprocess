/**
 * Expandable citation reference (Requirement 7 AC 6; AC-4.2.x).
 *
 * Shows document name and page; expands to reveal the snippet and relevance.
 */

import { useState } from "react";

import type { Citation } from "@/services/types";

export default function CitationCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.round((citation.relevanceScore ?? 0) * 100);

  return (
    <div className="rounded-md border border-slate-200 bg-white text-xs">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left"
      >
        <span className="truncate font-medium text-slate-700">
          {citation.documentName}
          {citation.pageNumber != null && (
            <span className="text-slate-400"> · p.{citation.pageNumber}</span>
          )}
        </span>
        <span className="shrink-0 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600">
          {pct}%
        </span>
      </button>
      {expanded && (
        <p className="border-t border-slate-100 px-2 py-1.5 text-slate-600">
          “{citation.snippet}”
        </p>
      )}
    </div>
  );
}
