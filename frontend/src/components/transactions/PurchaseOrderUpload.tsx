/**
 * Purchase Order upload form (ADMIN only).
 *
 * Upload a PO document to auto-fill the fields via BDA extraction, or enter
 * them manually, then save a structured PO record for three-way matching.
 * Calls `onUploaded` after a successful save so the parent can refresh the list.
 */

import { useState } from "react";

import ExtractUpload, { InlineSpinner } from "@/components/transactions/ExtractUpload";
import { adminApi } from "@/services/api";
import { ApiError } from "@/services/types";

type Feedback = { tone: "ok" | "err"; text: string } | null;

const inputCls =
  "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none";
const btnCls =
  "rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-60";

export default function PurchaseOrderUpload({ onUploaded }: { onUploaded?: () => void }) {
  const [po, setPo] = useState({ poNumber: "", vendorName: "", totalAmount: "", totalQuantity: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Feedback>(null);
  const [extracting, setExtracting] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const locked = extracting || busy;

  const extract = async (file: File) => {
    if (locked) return;
    setExtracting(true);
    setFileName(file.name);
    setMsg(null);
    try {
      const res = await adminApi.extractPurchaseOrder(file);
      setPo({
        poNumber: res.poNumber ?? "",
        vendorName: res.vendorName ?? "",
        totalAmount: res.totalAmount != null ? String(res.totalAmount) : "",
        totalQuantity: res.totalQuantity != null ? String(res.totalQuantity) : "",
      });
      const conf = res.overallConfidence != null ? ` · ${Math.round(res.overallConfidence * 100)}% confidence` : "";
      const filled = [res.poNumber, res.vendorName, res.totalAmount, res.totalQuantity].filter(
        (v) => v != null && v !== "",
      ).length;
      if (filled === 0) {
        setMsg({ tone: "err", text: "No fields could be read from that document. Enter the details manually." });
      } else {
        setMsg({ tone: "ok", text: `Auto-filled ${filled} of 4 fields${conf}. Review and edit before saving.` });
      }
    } catch (err) {
      setMsg({ tone: "err", text: err instanceof ApiError ? err.message : "Extraction failed." });
    } finally {
      setExtracting(false);
    }
  };

  const submit = async () => {
    const amount = Number(po.totalAmount);
    const quantity = Number(po.totalQuantity);
    if (
      !po.poNumber.trim() ||
      !po.vendorName.trim() ||
      !Number.isFinite(amount) ||
      amount <= 0 ||
      !Number.isFinite(quantity) ||
      quantity <= 0
    ) {
      setMsg({ tone: "err", text: "PO number, vendor, a positive amount, and a positive quantity are required." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await adminApi.uploadPurchaseOrder({
        poNumber: po.poNumber.trim(),
        vendorName: po.vendorName.trim(),
        totalAmount: amount,
        totalQuantity: quantity,
        fileName: fileName ?? undefined,
      });
      setMsg({ tone: "ok", text: `Purchase order ${po.poNumber.trim()} stored.` });
      setPo({ poNumber: "", vendorName: "", totalAmount: "", totalQuantity: "" });
      setFileName(null);
      onUploaded?.();
    } catch (err) {
      setMsg({ tone: "err", text: err instanceof ApiError ? err.message : "PO upload failed." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700">Upload purchase order</h2>
      <p className="mt-0.5 text-xs text-slate-400">Store a structured PO for three-way matching.</p>
      <div className="mt-3">
        <ExtractUpload
          heading="Upload a PO document to auto-fill the fields — or enter them manually below."
          busy={extracting}
          fileName={fileName}
          onFile={(f) => void extract(f)}
        />
        <fieldset disabled={locked} className="space-y-2 disabled:opacity-60">
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Purchase Order Number</span>
            <input className={inputCls} value={po.poNumber} onChange={(e) => setPo({ ...po, poNumber: e.target.value })} />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Vendor Name</span>
            <input className={inputCls} value={po.vendorName} onChange={(e) => setPo({ ...po, vendorName: e.target.value })} />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Total Amount (NZD)</span>
            <input
              type="number"
              min="0"
              step="0.01"
              className={inputCls}
              value={po.totalAmount}
              onChange={(e) => setPo({ ...po, totalAmount: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Total Quantity</span>
            <input
              type="number"
              min="0"
              step="1"
              className={inputCls}
              value={po.totalQuantity}
              onChange={(e) => setPo({ ...po, totalQuantity: e.target.value })}
            />
          </label>
          <button type="button" disabled={locked} onClick={() => void submit()} className={`${btnCls} inline-flex items-center gap-2`}>
            {busy && <InlineSpinner className="text-white" />}
            {busy ? "Saving…" : "Save purchase order"}
          </button>
        </fieldset>
        {msg && (
          <p role={msg.tone === "err" ? "alert" : "status"} className={`mt-2 text-sm ${msg.tone === "err" ? "text-red-700" : "text-green-700"}`}>
            {msg.text}
          </p>
        )}
      </div>
    </section>
  );
}
