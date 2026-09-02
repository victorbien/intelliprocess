/** Displays the three-way match outcome and any discrepancies (AC-3.5.x). */

import type { MatchResult } from "@/services/types";

interface MatchingResultProps {
  matchResult?: MatchResult | null;
}

function verdictTone(verdict?: string): string {
  const v = String(verdict ?? "").toUpperCase();
  if (v === "PASS" || v === "MATCHED" || v === "CONFIRMED") return "bg-green-100 text-green-700";
  if (v === "FAIL" || v === "NO_MATCH" || v === "NOT_RECEIVED") return "bg-red-100 text-red-700";
  return "bg-amber-100 text-amber-800";
}

/** Border/background tone for the PO / GR sub-status cards. */
function subTone(verdict?: string): string {
  const v = String(verdict ?? "").toUpperCase();
  if (v === "MATCHED" || v === "CONFIRMED") return "border-green-200 bg-green-50";
  if (v === "NO_MATCH" || v === "NOT_RECEIVED" || v === "FAIL") return "border-red-200 bg-red-50";
  return "border-slate-200 bg-slate-50";
}

/** Humanise enum-style statuses: NO_MATCH -> "No match", NOT_RECEIVED -> "Not received". */
function humanize(value?: unknown): string {
  const raw = String(value ?? "").trim();
  if (!raw || raw === "—") return "—";
  return raw
    .toLowerCase()
    .split(/[_\s]+/)
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

function subStatus(part?: Record<string, unknown>): string {
  return String(part?.status ?? "—");
}

export default function MatchingResult({ matchResult }: MatchingResultProps) {
  if (!matchResult) {
    return <p className="text-sm text-slate-400">Matching has not run for this invoice yet.</p>;
  }

  const threeWay = matchResult.threeWayMatch;
  const poStatus = subStatus(matchResult.poMatch);
  const grStatus = subStatus(matchResult.grMatch);
  const discrepancies = matchResult.discrepancies ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Three-way match
        </span>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${verdictTone(threeWay)}`}
        >
          {humanize(threeWay) || "Unknown"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className={`rounded-md border px-3 py-2 ${subTone(poStatus)}`}>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Purchase order</p>
          <p className="mt-0.5 font-semibold text-slate-800">{humanize(poStatus)}</p>
        </div>
        <div className={`rounded-md border px-3 py-2 ${subTone(grStatus)}`}>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Goods receipt</p>
          <p className="mt-0.5 font-semibold text-slate-800">{humanize(grStatus)}</p>
        </div>
      </div>

      {discrepancies.length > 0 && (
        <div className="rounded-md border border-red-100 bg-red-50 px-3 py-2">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-700">
            Discrepancies
          </p>
          <ul className="list-inside list-disc space-y-1 text-sm text-red-700">
            {discrepancies.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
