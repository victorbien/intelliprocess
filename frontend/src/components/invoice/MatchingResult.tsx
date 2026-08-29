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

function subStatus(part?: Record<string, unknown>): string {
  return String(part?.status ?? "—");
}

export default function MatchingResult({ matchResult }: MatchingResultProps) {
  if (!matchResult) {
    return <p className="text-sm text-slate-400">Matching has not run for this invoice yet.</p>;
  }

  const threeWay = matchResult.threeWayMatch;
  const discrepancies = matchResult.discrepancies ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm text-slate-500">Three-way match:</span>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${verdictTone(threeWay)}`}>
          {threeWay ?? "Unknown"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-md bg-slate-50 px-3 py-2">
          <p className="text-xs text-slate-400">Purchase order</p>
          <p className="font-medium text-slate-700">{subStatus(matchResult.poMatch)}</p>
        </div>
        <div className="rounded-md bg-slate-50 px-3 py-2">
          <p className="text-xs text-slate-400">Goods receipt</p>
          <p className="font-medium text-slate-700">{subStatus(matchResult.grMatch)}</p>
        </div>
      </div>

      {discrepancies.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase text-slate-400">Discrepancies</p>
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
