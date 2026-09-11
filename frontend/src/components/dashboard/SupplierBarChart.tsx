/**
 * Horizontal bar chart of top suppliers by total spend (AC-3.9.x).
 *
 * Uses a recharts BarChart with layout="vertical" so vendor names sit on the
 * Y axis and spend on the X axis.
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

import type { SupplierBreakdownItem } from "@/services/types";

const BAR_COLOR = "#4f46e5"; // indigo

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

interface SupplierBarChartProps {
  suppliers: SupplierBreakdownItem[];
}

export default function SupplierBarChart({ suppliers }: SupplierBarChartProps) {
  // Top suppliers by spend, highest first.
  const data = [...(suppliers ?? [])]
    .sort((a, b) => b.totalAmount - a.totalAmount)
    .slice(0, 8);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-700">Top suppliers by spend</h2>
      {data.length === 0 ? (
        <p className="flex h-64 items-center justify-center text-sm text-slate-400">
          No supplier data
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={256}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              tickFormatter={(value) => currency.format(Number(value))}
              fontSize={11}
            />
            <YAxis
              type="category"
              dataKey="vendorName"
              width={120}
              fontSize={11}
              tickFormatter={(value) => {
                const text = String(value);
                return text.length > 16 ? `${text.slice(0, 15)}…` : text;
              }}
            />
            <Tooltip
              formatter={(value) => currency.format(Number(value))}
            />
            <Bar dataKey="totalAmount" fill={BAR_COLOR} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
