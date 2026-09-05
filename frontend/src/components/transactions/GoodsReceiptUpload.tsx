/**
 * Goods Receipt upload form (ADMIN only).
 *
 * Upload a GR document to auto-fill the fields via BDA extraction, or enter
 * them manually, then save a structured GR record linked to an existing PO.
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

export default function GoodsReceiptUpload({ onUploaded }: { onUploaded?: () => void }) {
  const [gr, setGr] = useState({ grId: "", poNumber: "", totalQuantityReceived: "", totalAmount: "" });
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
      const res = await adminApi.extractGoodsReceipt(file);
      setGr({
        grId: res.grId ?? "",
        poNumber: res.poNumber ?? "",
        totalQuantityReceived: res.totalQuantityReceived != null ? String(res.totalQuantityReceived) : "",
        totalAmount: res.totalAmount != null ? String(res.totalAmount) : "",
      });
      const conf = res.overallConfidence != null ? ` · ${Math.round(res.overallConfidence * 100)}% confidence` : "";
      const filled = [res.grId, res.poNumber, res.totalQuantityReceived, res.totalAmount].filter(
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
    const qty = Number(gr.totalQuantityReceived);
    const amount = Number(gr.totalAmount);
    if (
      !gr.grId.trim() ||
      !gr.poNumber.trim() ||
      !Number.isFinite(qty) ||
      qty <= 0 ||
      !Number.isFinite(amount) ||
      amount <= 0
    ) {
      setMsg({ tone: "err", text: "GR id, PO number, a positive quantity, and a positive amount are required." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await adminApi.uploadGoodsReceipt({
        grId: gr.grId.trim(),
        poNumber: gr.poNumber.trim(),
        totalQuantityReceived: qty,
        totalAmount: amount,
        fileName: fileName ?? undefined,
      });
      setMsg({ tone: "ok", text: `Goods receipt ${gr.grId.trim()} linked to ${gr.poNumber.trim()}.` });
      setGr({ grId: "", poNumber: "", totalQuantityReceived: "", totalAmount: "" });
      setFileName(null);
      onUploaded?.();
    } catch (err) {
      setMsg({ tone: "err", text: err instanceof ApiError ? err.message : "GR upload failed." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700">Upload goods receipt</h2>
      <p className="mt-0.5 text-xs text-slate-400">Link a GR to an existing PO for three-way matching.</p>
      <div className="mt-3">
        <ExtractUpload
          heading="Upload a GR document to auto-fill the fields — or enter them manually below."
          busy={extracting}
          fileName={fileName}
          onFile={(f) => void extract(f)}
        />
        <fieldset disabled={locked} className="space-y-2 disabled:opacity-60">
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Goods Receipt Number/ID</span>
            <input className={inputCls} value={gr.grId} onChange={(e) => setGr({ ...gr, grId: e.target.value })} />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Purchase Order Number</span>
            <input className={inputCls} value={gr.poNumber} onChange={(e) => setGr({ ...gr, poNumber: e.target.value })} />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Total Amount (NZD)</span>
            <input
              type="number"
              min="0"
              step="0.01"
              className={inputCls}
              value={gr.totalAmount}
              onChange={(e) => setGr({ ...gr, totalAmount: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Total Quantity</span>
            <input
              type="number"
              min="0"
              step="1"
              className={inputCls}
              value={gr.totalQuantityReceived}
              onChange={(e) => setGr({ ...gr, totalQuantityReceived: e.target.value })}
            />
          </label>
          <button type="button" disabled={locked} onClick={() => void submit()} className={`${btnCls} inline-flex items-center gap-2`}>
            {busy && <InlineSpinner className="text-white" />}
            {busy ? "Saving…" : "Save goods receipt"}
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
