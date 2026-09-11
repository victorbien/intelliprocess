/**
 * "Upload a document to auto-fill the form" dropzone, shared by the Purchase
 * Order and Goods Receipt upload forms (ADMIN-only).
 *
 * While `busy`, the control is fully locked: no new file can be selected, and
 * a progress indicator replaces the picker so the wait reads as intentional.
 */

import { useRef } from "react";

/** Small inline spinner. */
export function InlineSpinner({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`h-4 w-4 animate-spin text-indigo-600 ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

export default function ExtractUpload({
  heading,
  busy,
  fileName,
  onFile,
}: {
  heading: string;
  busy: boolean;
  fileName: string | null;
  onFile: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      className={`mb-4 rounded-lg border border-dashed p-3 transition-colors ${
        busy ? "border-indigo-200 bg-indigo-50/40" : "border-slate-300 bg-slate-50"
      }`}
    >
      <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-600">
        <svg className="h-3.5 w-3.5 text-slate-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M10 3a1 1 0 01.7.3l3 3a1 1 0 01-1.4 1.4L11 5.4V13a1 1 0 11-2 0V5.4L7.7 7.7a1 1 0 01-1.4-1.4l3-3A1 1 0 0110 3z" />
          <path d="M4 14a1 1 0 011 1v1h10v-1a1 1 0 112 0v2a1 1 0 01-1 1H4a1 1 0 01-1-1v-2a1 1 0 011-1z" />
        </svg>
        {heading}
      </p>

      {busy ? (
        <div className="flex items-center gap-2 rounded-md bg-white/70 px-3 py-2">
          <InlineSpinner />
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-slate-700">
              Extracting{fileName ? ` from "${fileName}"` : ""}…
            </p>
            <p className="text-[11px] text-slate-400">This can take up to ~30 seconds. Please wait.</p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="shrink-0 rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 transition hover:bg-indigo-100"
            >
              Choose file…
            </button>
            <span className="truncate text-xs text-slate-500">
              {fileName ? fileName : "PDF, PNG, or JPEG"}
            </span>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
              e.target.value = ""; // allow re-selecting the same file
            }}
          />
        </>
      )}
    </div>
  );
}
