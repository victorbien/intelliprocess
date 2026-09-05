/** Purchase Order detail page (view-only for AP Clerk, Finance Manager, Admin). */

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import Spinner from "@/components/common/Spinner";
import ErrorAlert from "@/components/common/ErrorAlert";
import { purchaseOrdersApi } from "@/services/api";
import { ApiError, type PurchaseOrderDetail } from "@/services/types";
import { logger } from "@/services/logger";

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

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-700">{value ?? "—"}</dd>
    </div>
  );
}

export default function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [po, setPo] = useState<PurchaseOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await purchaseOrdersApi.detail(id);
      setPo(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load purchase order.";
      logger.error("purchase-order", "Detail load failed", err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Loading purchase order" />
      </div>
    );
  }

  if (error || !po) {
    return <ErrorAlert message={error ?? "Purchase order not found."} onRetry={() => void load()} />;
  }

  return (
    <div className="space-y-4">
      <div>
        <Link to="/purchase-orders" className="text-sm text-indigo-600 hover:underline">
          ← Back to purchase orders
        </Link>
        <h1 className="mt-1 break-words text-xl font-semibold text-slate-800">
          {po.fileName || po.poNumber}
        </h1>
        <p className="mt-1 text-xs text-slate-400">
          Uploaded by {po.uploadedBy ?? "—"}
          {po.uploadedAt && <> · {formatDateTime(po.uploadedAt)}</>}
        </p>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Purchase order details</h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="PO #" value={po.poNumber} />
          <Field label="Vendor Name" value={po.vendorName} />
          <Field label="Amount" value={formatAmount(po.totalAmount)} />
          <Field label="Quantity" value={formatQuantity(po.totalQuantity)} />
          <Field label="Currency" value={po.currency} />
          <Field label="Status" value={po.status} />
          <Field label="Department" value={po.department} />
          <Field label="Vendor ID" value={po.vendorId} />
          <Field label="Created Date" value={po.createdDate} />
          <Field label="Date & Time Uploaded" value={formatDateTime(po.uploadedAt)} />
        </dl>
      </section>
    </div>
  );
}
