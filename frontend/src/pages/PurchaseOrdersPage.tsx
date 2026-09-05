/**
 * Purchase Orders page.
 *
 * - View the list of all Purchase Orders (AP Clerk, Finance Manager, Admin).
 * - Upload a Purchase Order (Administrator only) — the form is moved here from
 *   the Admin page.
 */

import { useCallback, useEffect, useState } from "react";

import PurchaseOrderUpload from "@/components/transactions/PurchaseOrderUpload";
import TransactionTable, { type TransactionRow } from "@/components/transactions/TransactionTable";
import { useAuth } from "@/context/useAuth";
import { purchaseOrdersApi } from "@/services/api";
import { ApiError, type PurchaseOrderListItem } from "@/services/types";
import { logger } from "@/services/logger";

function toRow(po: PurchaseOrderListItem): TransactionRow {
  return {
    id: po.poNumber,
    detailPath: `/purchase-orders/${encodeURIComponent(po.poNumber)}`,
    fileName: po.fileName || po.poNumber,
    poNumber: po.poNumber,
    grNumber: null,
    vendorName: po.vendorName,
    amount: po.totalAmount,
    quantity: po.totalQuantity,
    uploadedBy: po.uploadedBy,
    uploadedAt: po.uploadedAt,
  };
}

export default function PurchaseOrdersPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("ADMIN");

  const [items, setItems] = useState<PurchaseOrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await purchaseOrdersApi.list();
      setItems(res.items);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load purchase orders.";
      logger.error("purchase-orders", "List failed", err);
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
        <h1 className="text-xl font-semibold text-slate-800">Purchase Orders</h1>
        <p className="text-sm text-slate-500">
          {isAdmin
            ? "Upload and review purchase orders used for three-way matching."
            : "Review purchase orders used for three-way matching."}
        </p>
      </div>

      {isAdmin && <PurchaseOrderUpload onUploaded={() => void load()} />}

      <TransactionTable
        title="Purchase Orders"
        rows={items.map(toRow)}
        loading={loading}
        error={error}
        emptyMessage="No purchase orders found."
        onRetry={() => void load()}
      />
    </div>
  );
}
