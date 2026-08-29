/** Colored badge for invoice statuses (AC-2.3.x). */

import type { InvoiceStatus } from "@/services/types";

const STYLES: Record<InvoiceStatus, string> = {
  UPLOADED: "bg-slate-100 text-slate-700",
  PROCESSING: "bg-blue-100 text-blue-700",
  EXTRACTED: "bg-indigo-100 text-indigo-700",
  APPROVED: "bg-green-100 text-green-700",
  ESCALATED: "bg-amber-100 text-amber-800",
  REJECTED: "bg-red-100 text-red-700",
  ERROR: "bg-red-100 text-red-700",
};

const LABELS: Record<InvoiceStatus, string> = {
  UPLOADED: "Uploaded",
  PROCESSING: "Processing",
  EXTRACTED: "Extracted",
  APPROVED: "Approved",
  ESCALATED: "Escalated",
  REJECTED: "Rejected",
  ERROR: "Error",
};

export default function StatusBadge({ status }: { status: InvoiceStatus | string }) {
  const key = String(status).toUpperCase() as InvoiceStatus;
  const style = STYLES[key] ?? "bg-slate-100 text-slate-700";
  const label = LABELS[key] ?? String(status);

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}
    >
      {label}
    </span>
  );
}
