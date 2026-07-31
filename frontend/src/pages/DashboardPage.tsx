import { useEffect, useState } from "react";
import { api } from "../services/api";

interface Stats {
  totalInvoices: number;
  statusCounts: Record<string, number>;
  autoApprovalRate: number;
  avgProcessingTimeSec: number;
  recentActivity: Array<{
    documentId: string;
    fileName: string;
    action: string;
    timestamp: string;
    actor: string;
  }>;
}

const STATUS_COLOUR: Record<string, string> = {
  APPROVED:   "text-green-600",
  ESCALATED:  "text-orange-500",
  REJECTED:   "text-red-500",
  ERROR:      "text-red-400",
  PROCESSING: "text-yellow-500",
  UPLOADED:   "text-blue-500",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/dashboard/stats")
      .then(({ data }) => setStats(data.data))
      .catch((err) => {
        const msg = err?.response?.data?.error ?? "Dashboard not yet available.";
        setError(msg);
      });
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-4 text-sm text-yellow-800">
          <strong>Note:</strong> {error}
          <br />
          <span className="text-xs text-yellow-600">
            Dashboard stats are part of Module 4. The API endpoint is not yet implemented.
          </span>
        </div>
      )}

      {stats && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Total Invoices" value={stats.totalInvoices} />
            <StatCard label="Auto-Approval Rate" value={`${stats.autoApprovalRate}%`} />
            <StatCard label="Avg Processing" value={`${stats.avgProcessingTimeSec}s`} />
            <StatCard
              label="Escalated"
              value={stats.statusCounts.ESCALATED ?? 0}
              highlight="orange"
            />
          </div>

          {/* Status breakdown */}
          <div className="bg-white border rounded-lg shadow-sm p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Status Breakdown</h2>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
              {Object.entries(stats.statusCounts).map(([status, count]) => (
                <div key={status} className="text-center">
                  <div className={`text-2xl font-bold ${STATUS_COLOUR[status] ?? "text-gray-600"}`}>
                    {count}
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">{status}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent activity */}
          {stats.recentActivity?.length > 0 && (
            <div className="bg-white border rounded-lg shadow-sm p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Recent Activity</h2>
              <ul className="space-y-1.5">
                {stats.recentActivity.map((a, i) => (
                  <li key={i} className="text-xs text-gray-600 flex gap-2">
                    <span className="text-gray-400 tabular-nums">
                      {new Date(a.timestamp).toLocaleTimeString()}
                    </span>
                    <span className="font-medium">{a.fileName}</span>
                    <span>{a.action}</span>
                    <span className="text-gray-400">by {a.actor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {/* Module status panel */}
      {!stats && !error && (
        <p className="text-gray-500 text-sm">Loading…</p>
      )}

      <ModuleStatus />
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number;
  highlight?: string;
}) {
  const valClass =
    highlight === "orange" ? "text-orange-500" :
    highlight === "red"    ? "text-red-500" :
    "text-gray-800";
  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <div className={`text-2xl font-bold ${valClass}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

function ModuleStatus() {
  const modules = [
    { name: "Module 1: Shared (Auth, Upload, Storage)", done: true },
    { name: "Module 2: AP Invoice Processing Engine",   done: false },
    { name: "Module 3: RAG Records Assistant",          done: false },
    { name: "Module 4: Dashboard & Admin",               done: false },
    { name: "Module 5: Frontend UI",                    done: false },
  ];
  return (
    <div className="bg-white border rounded-lg shadow-sm p-5">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">Implementation Progress</h2>
      <ul className="space-y-2">
        {modules.map((m) => (
          <li key={m.name} className="flex items-center gap-2 text-sm">
            <span className={m.done ? "text-green-500" : "text-gray-300"}>
              {m.done ? "✅" : "⬜"}
            </span>
            <span className={m.done ? "text-gray-700" : "text-gray-400"}>{m.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
