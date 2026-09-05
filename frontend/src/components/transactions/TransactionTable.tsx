/**
 * Shared table for Purchase Orders and Goods Receipts (view for AP Clerk,
 * Finance Manager, Administrator).
 *
 * Columns (per spec):
 *   File Name (links to detail) · PO# · GR# · Vendor Name · Amount ·
 *   Quantity · Uploaded by · Date and Time Uploaded
 *
 * The same table serves both transaction types; the parent supplies rows in a
 * normalised shape so PO# / GR# render correctly for each.
 */

import { Link } from "react-router-dom";

import Spinner from "@/components/common/Spinner";
import ErrorAlert from "@/components/common/ErrorAlert";

/** A normalised row shared by both PO and GR tables. */
export interface TransactionRow {
  /** Stable identifier used as the React key and detail-link segment. */
  id: string;
  /** Detail route, e.g. `/purchase-orders/PO-1`. */
  detailPath: string;
  fileName: string;
  poNumber?: string | null;
  grNumber?: string | null;
  vendorName?: string | null;
  amount?: number | null;
  quantity?: number | null;
  uploadedBy?: string | null;
  uploadedAt?: string | null;
}

interface TransactionTableProps {
  title: string;
  rows: TransactionRow[];
  loading: boolean;
  error: string | null;
  emptyMessage: string;
  onRetry: () => void;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-AU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatAmount(amount?: number | null): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(amount);
}

function formatQuantity(qty?: number | null): string {
  if (qty == null) return "—";
  return Number.isInteger(qty) ? String(qty) : qty.toFixed(2);
}

export default function TransactionTable({
  title,
  rows,
  loading,
  error,
  emptyMessage,
  onRetry,
}: TransactionTableProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
        <span className="text-xs text-slate-400">{rows.length} record{rows.length === 1 ? "" : "s"}</span>
      </div>

      {loading ? (
        <div className="p-6">
          <Spinner label={`Loading ${title.toLowerCase()}`} />
        </div>
      ) : error ? (
        <div className="p-4">
          <ErrorAlert message={error} onRetry={onRetry} />
        </div>
      ) : rows.length === 0 ? (
        <p className="p-6 text-center text-sm text-slate-400">{emptyMessage}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">File Name</th>
                <th className="px-4 py-2 font-medium">PO #</th>
                <th className="px-4 py-2 font-medium">GR #</th>
                <th className="px-4 py-2 font-medium">Vendor Name</th>
                <th className="px-4 py-2 font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Quantity</th>
                <th className="px-4 py-2 font-medium">Uploaded By</th>
                <th className="px-4 py-2 font-medium">Date &amp; Time Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link to={row.detailPath} className="font-medium text-indigo-600 hover:underline">
                      {row.fileName}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{row.poNumber ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-600">{row.grNumber ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-600">{row.vendorName ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-600">{formatAmount(row.amount)}</td>
                  <td className="px-4 py-2 text-slate-600">{formatQuantity(row.quantity)}</td>
                  <td className="px-4 py-2 text-slate-500">{row.uploadedBy ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-500">{formatDateTime(row.uploadedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
