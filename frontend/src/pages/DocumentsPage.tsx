/**
 * Knowledge Base documents list (all authenticated users).
 *
 * Read-only browse with optional category filter. Uploading and KB sync are
 * admin actions available on the Admin page.
 */

import { useCallback, useEffect, useState } from "react";

import Spinner from "@/components/common/Spinner";
import ErrorAlert from "@/components/common/ErrorAlert";
import { documentsApi } from "@/services/api";
import {
  ApiError,
  type DocumentCategory,
  type DocumentListItem,
} from "@/services/types";
import { logger } from "@/services/logger";

const CATEGORIES: (DocumentCategory | "all")[] = [
  "all",
  "policies",
  "contracts",
  "finance",
  "procurement",
  "general",
];

function syncTone(status?: string | null): string {
  switch ((status ?? "").toUpperCase()) {
    case "SYNCED":
      return "bg-green-100 text-green-700";
    case "PENDING":
      return "bg-amber-100 text-amber-800";
    case "FAILED":
      return "bg-red-100 text-red-700";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export default function DocumentsPage() {
  const [items, setItems] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<DocumentCategory | "all">("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await documentsApi.list(category === "all" ? undefined : category);
      setItems(res.items);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load documents.";
      logger.error("documents", "List failed", err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Documents</h1>
        <p className="text-sm text-slate-500">
          Organizational documents available to the Records Assistant.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-700">Knowledge Base</h2>
          <label className="flex items-center gap-2 text-sm text-slate-500">
            Category
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as DocumentCategory | "all")}
              className="rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-indigo-500 focus:outline-none"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c === "all" ? "All" : c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <div className="p-6">
            <Spinner label="Loading documents" />
          </div>
        ) : error ? (
          <div className="p-4">
            <ErrorAlert message={error} onRetry={() => void load()} />
          </div>
        ) : items.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-400">No documents found.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Description</th>
                <th className="px-4 py-2 font-medium">KB status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <tr key={doc.documentId} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="px-4 py-2 font-medium text-slate-700">{doc.fileName}</td>
                  <td className="px-4 py-2 capitalize text-slate-600">{doc.category}</td>
                  <td className="px-4 py-2 text-slate-500">{doc.description ?? "—"}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${syncTone(doc.kbSyncStatus)}`}>
                      {doc.kbSyncStatus ?? "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
