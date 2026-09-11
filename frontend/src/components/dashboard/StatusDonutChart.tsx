/**
 * Donut chart of invoice status distribution (AC-3.9.x).
 *
 * Renders a recharts PieChart with an inner radius (donut). Only statuses with
 * a non-zero count are shown. Each status has a fixed color.
 */

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const STATUS_COLORS: Record<string, string> = {
  approved: "#16a34a",
  escalated: "#d97706",
  rejected: "#dc2626",
  error: "#991b1b",
  processing: "#ca8a04",
  extracted: "#0891b2",
  uploaded: "#2563eb",
  unknown: "#64748b",
};

function colorFor(status: string): string {
  return STATUS_COLORS[status.toLowerCase()] ?? STATUS_COLORS.unknown;
}

function label(status: string): string {
  const s = status.toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

interface StatusDonutChartProps {
  statusCounts: Record<string, number>;
}

export default function StatusDonutChart({ statusCounts }: StatusDonutChartProps) {
  const data = Object.entries(statusCounts ?? {})
    .filter(([, count]) => count > 0)
    .map(([status, count]) => ({ name: label(status), value: count, status }));

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-700">Invoice status</h2>
      {data.length === 0 ? (
        <p className="flex h-64 items-center justify-center text-sm text-slate-400">
          No status data
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={256}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={90}
              paddingAngle={2}
            >
              {data.map((entry) => (
                <Cell key={entry.status} fill={colorFor(entry.status)} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
