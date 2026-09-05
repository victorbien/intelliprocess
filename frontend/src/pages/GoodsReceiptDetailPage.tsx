/** Goods Receipt detail page (view-only for AP Clerk, Finance Manager, Admin). */

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import Spinner from "@/components/common/Spinner";
import ErrorAlert from "@/components/common/ErrorAlert";
import { goodsReceiptsApi } from "@/services/api";
import { ApiError, type GoodsReceiptDetail } from "@/services/types";
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

export default function GoodsReceiptDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [gr, setGr] = useState<GoodsReceiptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await goodsReceiptsApi.detail(id);
      setGr(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load goods receipt.";
      logger.error("goods-receipt", "Detail load failed", err);
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
        <Spinner label="Loading goods receipt" />
      </div>
    );
  }

  if (error || !gr) {
    return <ErrorAlert message={error ?? "Goods receipt not found."} onRetry={() => void load()} />;
  }

  return (
    <div className="space-y-4">
      <div>
        <Link to="/goods-receipts" className="text-sm text-indigo-600 hover:underline">
          ← Back to goods receipts
        </Link>
        <h1 className="mt-1 break-words text-xl font-semibold text-slate-800">
          {gr.fileName || gr.grId}
        </h1>
        <p className="mt-1 text-xs text-slate-400">
          Uploaded by {gr.uploadedBy ?? "—"}
          {gr.uploadedAt && <> · {formatDateTime(gr.uploadedAt)}</>}
        </p>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Goods receipt details</h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="GR #" value={gr.grId} />
          <Field label="PO #" value={gr.poNumber} />
          <Field label="Vendor Name" value={gr.vendorName} />
          <Field label="Amount" value={formatAmount(gr.totalAmount)} />
          <Field label="Quantity" value={formatQuantity(gr.totalQuantityReceived)} />
          <Field label="Status" value={gr.status} />
          <Field label="Received Date" value={gr.receivedDate} />
          <Field label="Date & Time Uploaded" value={formatDateTime(gr.uploadedAt)} />
        </dl>
      </section>
    </div>
  );
}
