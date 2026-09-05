/**
 * Goods Receipts page.
 *
 * - View the list of all Goods Receipts (AP Clerk, Finance Manager, Admin).
 * - Upload a Goods Receipt (Administrator only) — the form is moved here from
 *   the Admin page.
 */

import { useCallback, useEffect, useState } from "react";

import GoodsReceiptUpload from "@/components/transactions/GoodsReceiptUpload";
import TransactionTable, { type TransactionRow } from "@/components/transactions/TransactionTable";
import { useAuth } from "@/context/useAuth";
import { goodsReceiptsApi } from "@/services/api";
import { ApiError, type GoodsReceiptListItem } from "@/services/types";
import { logger } from "@/services/logger";

function toRow(gr: GoodsReceiptListItem): TransactionRow {
  return {
    id: gr.grId,
    detailPath: `/goods-receipts/${encodeURIComponent(gr.grId)}`,
    fileName: gr.fileName || gr.grId,
    poNumber: gr.poNumber,
    grNumber: gr.grId,
    vendorName: gr.vendorName,
    amount: gr.totalAmount,
    quantity: gr.totalQuantityReceived,
    uploadedBy: gr.uploadedBy,
    uploadedAt: gr.uploadedAt,
  };
}

export default function GoodsReceiptsPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("ADMIN");

  const [items, setItems] = useState<GoodsReceiptListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await goodsReceiptsApi.list();
      setItems(res.items);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load goods receipts.";
      logger.error("goods-receipts", "List failed", err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Goods Receipts</h1>
        <p className="text-sm text-slate-500">
          {isAdmin
            ? "Upload and review goods receipts used for three-way matching."
            : "Review goods receipts used for three-way matching."}
        </p>
      </div>

      {isAdmin && <GoodsReceiptUpload onUploaded={() => void load()} />}

      <TransactionTable
        title="Goods Receipts"
        rows={items.map(toRow)}
        loading={loading}
        error={error}
        emptyMessage="No goods receipts found."
        onRetry={() => void load()}
      />
    </div>
  );
}
