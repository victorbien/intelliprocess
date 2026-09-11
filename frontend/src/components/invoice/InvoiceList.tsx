/**
 * Invoice list table (AC-2.3.x).
 *
 * Displays invoices with status badges and links to detail. Supports an
 * optional status filter and manual refresh. Data fetching is owned by the
 * parent via props so the list can be refreshed after an upload.
 */

import { Link } from "react-router-dom";

import StatusBadge from "@/components/common/StatusBadge";
import Spinner from "@/components/common/Spinner";
import ErrorAlert from "@/components/common/ErrorAlert";
import type { InvoiceListItem, InvoiceStatus } from "@/services/types";

const STATUS_OPTIONS: (InvoiceStatus | "ALL")[] = [
  "ALL",
  "UPLOADED",
  "PROCESSING",
  "EXTRACTED",
  "APPROVED",
  "ESCALATED",
  "REJECTED",
  "ERROR",
];

interface InvoiceListProps {
  items: InvoiceListItem[];
  loading: boolean;
  error: string | null;
  statusFilter: InvoiceStatus | "ALL";
  onStatusFilterChange: (status: InvoiceStatus | "ALL") => void;
  onRetry: () => void;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function formatAmount(amount?: number | null): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(amount);
}

export default function InvoiceList({
  items,
  loading,
  error,
  statusFilter,
  onStatusFilterChange,
  onRetry,
}: InvoiceListProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-700">Invoices</h2>
        <label className="flex items-center gap-2 text-sm text-slate-500">
          Status
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value as InvoiceStatus | "ALL")}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-indigo-500 focus:outline-none"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s === "ALL" ? "All" : s.charAt(0) + s.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <div className="p-6">
          <Spinner label="Loading invoices" />
        </div>
      ) : error ? (
        <div className="p-4">
          <ErrorAlert message={error} onRetry={onRetry} />
        </div>
      ) : items.length === 0 ? (
        <p className="p-6 text-center text-sm text-slate-400">No invoices found.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-100 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">File</th>
              <th className="px-4 py-2 font-medium">Vendor</th>
              <th className="px-4 py-2 font-medium">Amount</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {items.map((inv) => (
              <tr key={inv.documentId} className="border-b border-slate-50 hover:bg-slate-50">
                <td className="px-4 py-2">
                  <Link
                    to={`/invoices/${inv.documentId}`}
                    className="font-medium text-indigo-600 hover:underline"
                  >
                    {inv.fileName}
                  </Link>
                </td>
                <td className="px-4 py-2 text-slate-600">{inv.vendorName ?? "—"}</td>
                <td className="px-4 py-2 text-slate-600">{formatAmount(inv.totalAmount)}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={inv.status} />
                </td>
                <td className="px-4 py-2 text-slate-500">{formatDate(inv.uploadedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
