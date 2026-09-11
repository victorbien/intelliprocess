/**
 * Auto-approval rate gauge (AC-3.9.x).
 *
 * Shows the auto-approval rate as a big number inside a green progress ring,
 * with an optional three-way match summary underneath. The ring is a simple
 * SVG circle so it renders crisply at any size.
 */

import type { MatchRateSummary } from "@/services/types";

const RING_COLOR = "#16a34a"; // green
const TRACK_COLOR = "#e2e8f0"; // slate-200

interface AutoApprovalGaugeProps {
  rate: number;
  matchRate?: MatchRateSummary | null;
}

export default function AutoApprovalGauge({ rate, matchRate }: AutoApprovalGaugeProps) {
  const clamped = Math.max(0, Math.min(100, rate));
  const radius = 70;
  const stroke = 12;
  const size = (radius + stroke) * 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - clamped / 100);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-700">Auto-approval rate</h2>
      <div className="flex h-64 flex-col items-center justify-center gap-3">
        <div className="relative" style={{ width: size, height: size }}>
          <svg width={size} height={size} className="-rotate-90">
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={TRACK_COLOR}
              strokeWidth={stroke}
            />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={RING_COLOR}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-3xl font-bold text-slate-800">{clamped.toFixed(1)}%</span>
          </div>
        </div>

        {matchRate ? (
          <p className="text-sm text-slate-500">
            Three-way match: {matchRate.rate.toFixed(1)}% ({matchRate.matched}/{matchRate.total})
          </p>
        ) : null}
      </div>
    </div>
  );
}
