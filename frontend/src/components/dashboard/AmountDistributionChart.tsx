/**
 * Vertical bar chart of invoice amount distribution across buckets (AC-3.9.x).
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AmountBucket } from "@/services/types";

const BAR_COLOR = "#0d9488"; // teal

interface AmountDistributionChartProps {
  buckets: AmountBucket[];
}

export default function AmountDistributionChart({ buckets }: AmountDistributionChartProps) {
  const data = buckets ?? [];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-700">Invoice amount distribution</h2>
      {data.length === 0 ? (
        <p className="flex h-64 items-center justify-center text-sm text-slate-400">
          No amount data
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={256}>
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="bucket" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip />
            <Bar dataKey="count" fill={BAR_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
