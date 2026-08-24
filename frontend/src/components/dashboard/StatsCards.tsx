/**
 * Summary stat cards (AC-3.9.1).
 *
 * Shows total processed plus the key status counts (auto-approved, escalated,
 * rejected, pending) and headline rates.
 */

import type { DashboardStats } from "@/services/types";

interface StatCard {
  label: string;
  value: string;
  tone: string;
}

function pending(counts: Record<string, number>): number {
  // "Pending" = anything still in-flight (not a terminal decision).
  return (counts.uploaded ?? 0) + (counts.processing ?? 0) + (counts.extracted ?? 0);
}

export default function StatsCards({ stats }: { stats: DashboardStats }) {
  const c = stats.statusCounts ?? {};

  const cards: StatCard[] = [
    { label: "Total invoices", value: String(stats.totalInvoices), tone: "text-slate-800" },
    { label: "Auto-approved", value: String(c.approved ?? 0), tone: "text-green-600" },
    { label: "Escalated", value: String(c.escalated ?? 0), tone: "text-amber-600" },
    { label: "Rejected", value: String(c.rejected ?? 0), tone: "text-red-600" },
    { label: "Pending", value: String(pending(c)), tone: "text-blue-600" },
    {
      label: "Auto-approval rate",
      value: `${stats.autoApprovalRate.toFixed(1)}%`,
      tone: "text-indigo-600",
    },
    {
      label: "Avg processing",
      value: `${stats.avgProcessingTimeSec.toFixed(1)}s`,
      tone: "text-slate-800",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-slate-400">{card.label}</p>
          <p className={`mt-1 text-2xl font-bold ${card.tone}`}>{card.value}</p>
        </div>
      ))}
    </div>
  );
}
