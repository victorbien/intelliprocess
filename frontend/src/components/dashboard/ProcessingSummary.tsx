/** Recent activity feed for the dashboard (AC-3.9.2, US-5.2). */

import { Link } from "react-router-dom";

import type { RecentActivityItem } from "@/services/types";

interface ProcessingSummaryProps {
  activity: RecentActivityItem[];
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export default function ProcessingSummary({ activity }: ProcessingSummaryProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700">
        Recent activity
      </h2>

      {activity.length === 0 ? (
        <p className="p-6 text-center text-sm text-slate-400">No recent activity.</p>
      ) : (
        <ul className="divide-y divide-slate-50">
          {activity.map((item) => (
            <li key={`${item.documentId}-${item.timestamp}`} className="flex items-center justify-between px-4 py-2.5">
              <div className="min-w-0">
                <Link
                  to={`/invoices/${item.documentId}`}
                  className="truncate text-sm font-medium text-indigo-600 hover:underline"
                >
                  {item.fileName || item.documentId}
                </Link>
                <p className="text-xs text-slate-500">
                  {item.action} · {item.actor}
                </p>
              </div>
              <span className="shrink-0 text-xs text-slate-400">{formatTime(item.timestamp)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
