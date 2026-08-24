/** Invoices page: upload + filterable list (tasks 5.2, 5.3). */

import { useCallback, useEffect, useState } from "react";

import InvoiceUpload from "@/components/invoice/InvoiceUpload";
import InvoiceList from "@/components/invoice/InvoiceList";
import { invoicesApi } from "@/services/api";
import { ApiError, type InvoiceListItem, type InvoiceStatus } from "@/services/types";
import { logger } from "@/services/logger";

export default function InvoicesPage() {
  const [items, setItems] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "ALL">("ALL");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await invoicesApi.list(
        statusFilter === "ALL" ? { limit: 50 } : { status: statusFilter, limit: 50 },
      );
      setItems(res.items);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load invoices.";
      logger.error("invoices", "List failed", err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Invoices</h1>
        <p className="text-sm text-slate-500">
          Upload an invoice to start automated three-way matching and approval.
        </p>
      </div>

      <InvoiceUpload onUploaded={() => void load()} />

      <InvoiceList
        items={items}
        loading={loading}
        error={error}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        onRetry={() => void load()}
      />
    </div>
  );
}
