/**
 * Admin page (task 5.6, AC-5.1.x, FR-CROSS-001).
 *
 * ADMIN-only actions:
 *  - View and edit approval settings (amount/confidence thresholds, PO/GR match tolerances)
 *  - Upload a Knowledge Base document
 *  - Trigger a KB sync
 *  - Seed sample PO/GR data
 *  - Upload a structured Purchase Order
 *  - Upload a structured Goods Receipt
 */

import { useEffect, useRef, useState, type ReactNode } from "react";

import DocumentUpload from "@/components/admin/DocumentUpload";
import { adminApi, documentsApi } from "@/services/api";
import { ApiError, type ApprovalSettings } from "@/services/types";
import { logger } from "@/services/logger";

/** Small inline spinner. */
function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`h-4 w-4 animate-spin text-indigo-600 ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

/**
 * "Upload a document to auto-fill the form" dropzone.
 *
 * While `busy`, the control is fully locked: no new file can be selected, and
 * a progress indicator replaces the picker so the wait reads as intentional.
 */
function ExtractUpload({
  heading,
  busy,
  fileName,
  onFile,
}: {
  heading: string;
  busy: boolean;
  fileName: string | null;
  onFile: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      className={`mb-4 rounded-lg border border-dashed p-3 transition-colors ${
        busy ? "border-indigo-200 bg-indigo-50/40" : "border-slate-300 bg-slate-50"
      }`}
    >
      <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-600">
        <svg className="h-3.5 w-3.5 text-slate-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M10 3a1 1 0 01.7.3l3 3a1 1 0 01-1.4 1.4L11 5.4V13a1 1 0 11-2 0V5.4L7.7 7.7a1 1 0 01-1.4-1.4l3-3A1 1 0 0110 3z" />
          <path d="M4 14a1 1 0 011 1v1h10v-1a1 1 0 112 0v2a1 1 0 01-1 1H4a1 1 0 01-1-1v-2a1 1 0 011-1z" />
        </svg>
        {heading}
      </p>

      {busy ? (
        <div className="flex items-center gap-2 rounded-md bg-white/70 px-3 py-2">
          <Spinner />
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-slate-700">
              Extracting{fileName ? ` from "${fileName}"` : ""}…
            </p>
            <p className="text-[11px] text-slate-400">This can take up to ~30 seconds. Please wait.</p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="shrink-0 rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 transition hover:bg-indigo-100"
            >
              Choose file…
            </button>
            <span className="truncate text-xs text-slate-500">
              {fileName ? fileName : "PDF, PNG, or JPEG"}
            </span>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
              e.target.value = ""; // allow re-selecting the same file
            }}
          />
        </>
      )}
    </div>
  );
}

type Feedback = { tone: "ok" | "err"; text: string } | null;

function Card({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
      <p className="mt-0.5 text-xs text-slate-400">{description}</p>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function FeedbackLine({ feedback }: { feedback: Feedback }) {
  if (!feedback) return null;
  return (
    <p
      role={feedback.tone === "err" ? "alert" : "status"}
      className={`mt-2 text-sm ${feedback.tone === "err" ? "text-red-700" : "text-green-700"}`}
    >
      {feedback.text}
    </p>
  );
}

export default function AdminPage() {
  // ── KB sync ────────────────────────────────────────────────────────────────
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<Feedback>(null);

  const runSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await documentsApi.sync();
      logger.info("admin", `KB sync started: ${res.syncJobId ?? "n/a"}`);
      setSyncMsg({ tone: "ok", text: res.message });
    } catch (err) {
      setSyncMsg({ tone: "err", text: err instanceof ApiError ? err.message : "Sync failed." });
    } finally {
      setSyncing(false);
    }
  };

  // ── Seed data ────────────────────────────────────────────────────────────────
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<Feedback>(null);

  const runSeed = async () => {
    setSeeding(true);
    setSeedMsg(null);
    try {
      const res = await adminApi.seedData();
      setSeedMsg({
        tone: "ok",
        text: `${res.message} (${res.purchaseOrdersCreated} POs, ${res.goodsReceiptsCreated} GRs)`,
      });
    } catch (err) {
      setSeedMsg({ tone: "err", text: err instanceof ApiError ? err.message : "Seeding failed." });
    } finally {
      setSeeding(false);
    }
  };

  // ── PO upload ────────────────────────────────────────────────────────────────
  const [po, setPo] = useState({ poNumber: "", vendorName: "", totalAmount: "", totalQuantity: "" });
  const [poBusy, setPoBusy] = useState(false);
  const [poMsg, setPoMsg] = useState<Feedback>(null);
  const [poExtracting, setPoExtracting] = useState(false);
  const [poFileName, setPoFileName] = useState<string | null>(null);
  const poLocked = poExtracting || poBusy;

  const extractPo = async (file: File) => {
    if (poLocked) return; // guard against concurrent uploads while busy
    setPoExtracting(true);
    setPoFileName(file.name);
    setPoMsg(null);
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
        setPoMsg({ tone: "err", text: "No fields could be read from that document. Enter the details manually." });
      } else {
        setPoMsg({ tone: "ok", text: `Auto-filled ${filled} of 4 fields${conf}. Review and edit before saving.` });
      }
    } catch (err) {
      setPoMsg({ tone: "err", text: err instanceof ApiError ? err.message : "Extraction failed." });
    } finally {
      setPoExtracting(false);
    }
  };

  const submitPo = async () => {
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
      setPoMsg({
        tone: "err",
        text: "PO number, vendor, a positive amount, and a positive quantity are required.",
      });
      return;
    }
    setPoBusy(true);
    setPoMsg(null);
    try {
      await adminApi.uploadPurchaseOrder({
        poNumber: po.poNumber.trim(),
        vendorName: po.vendorName.trim(),
        totalAmount: amount,
        totalQuantity: quantity,
      });
      setPoMsg({ tone: "ok", text: `Purchase order ${po.poNumber.trim()} stored.` });
      setPo({ poNumber: "", vendorName: "", totalAmount: "", totalQuantity: "" });
    } catch (err) {
      setPoMsg({ tone: "err", text: err instanceof ApiError ? err.message : "PO upload failed." });
    } finally {
      setPoBusy(false);
    }
  };

  // ── GR upload ────────────────────────────────────────────────────────────────
  const [gr, setGr] = useState({ grId: "", poNumber: "", totalQuantityReceived: "", totalAmount: "" });
  const [grBusy, setGrBusy] = useState(false);
  const [grMsg, setGrMsg] = useState<Feedback>(null);
  const [grExtracting, setGrExtracting] = useState(false);
  const [grFileName, setGrFileName] = useState<string | null>(null);
  const grLocked = grExtracting || grBusy;

  const extractGr = async (file: File) => {
    if (grLocked) return; // guard against concurrent uploads while busy
    setGrExtracting(true);
    setGrFileName(file.name);
    setGrMsg(null);
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
        setGrMsg({ tone: "err", text: "No fields could be read from that document. Enter the details manually." });
      } else {
        setGrMsg({ tone: "ok", text: `Auto-filled ${filled} of 4 fields${conf}. Review and edit before saving.` });
      }
    } catch (err) {
      setGrMsg({ tone: "err", text: err instanceof ApiError ? err.message : "Extraction failed." });
    } finally {
      setGrExtracting(false);
    }
  };

  const submitGr = async () => {
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
      setGrMsg({
        tone: "err",
        text: "GR id, PO number, a positive quantity, and a positive amount are required.",
      });
      return;
    }
    setGrBusy(true);
    setGrMsg(null);
    try {
      await adminApi.uploadGoodsReceipt({
        grId: gr.grId.trim(),
        poNumber: gr.poNumber.trim(),
        totalQuantityReceived: qty,
        totalAmount: amount,
      });
      setGrMsg({ tone: "ok", text: `Goods receipt ${gr.grId.trim()} linked to ${gr.poNumber.trim()}.` });
      setGr({ grId: "", poNumber: "", totalQuantityReceived: "", totalAmount: "" });
    } catch (err) {
      setGrMsg({ tone: "err", text: err instanceof ApiError ? err.message : "GR upload failed." });
    } finally {
      setGrBusy(false);
    }
  };

  // ── Approval settings (thresholds & tolerances) ──────────────────────────────
  const [settings, setSettings] = useState<ApprovalSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<Feedback>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await adminApi.getSettings();
        if (active) setSettings(res);
      } catch (err) {
        if (active)
          setSettingsMsg({
            tone: "err",
            text: err instanceof ApiError ? err.message : "Failed to load settings.",
          });
      } finally {
        if (active) setSettingsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const submitSettings = async () => {
    if (!settings) return;
    const { amountThreshold, confidenceThreshold, poAmountTolerance, grQtyTolerance } = settings;
    // Client-side range checks mirror the backend schema (ge/le).
    if (!Number.isFinite(amountThreshold) || amountThreshold < 0) {
      setSettingsMsg({ tone: "err", text: "Amount threshold must be 0 or greater." });
      return;
    }
    for (const [label, v] of [
      ["Confidence Threshold", confidenceThreshold],
      ["Total Amount Tolerance", poAmountTolerance],
      ["Total Quantity Tolerance", grQtyTolerance],
    ] as const) {
      if (!Number.isFinite(v) || v < 0 || v > 1) {
        setSettingsMsg({ tone: "err", text: `${label} must be between 0 and 1.` });
        return;
      }
    }
    setSettingsBusy(true);
    setSettingsMsg(null);
    try {
      const saved = await adminApi.updateSettings({
        amountThreshold,
        confidenceThreshold,
        poAmountTolerance,
        grQtyTolerance,
      });
      setSettings(saved);
      logger.info("admin", "Approval settings updated");
      setSettingsMsg({ tone: "ok", text: "Approval settings saved." });
    } catch (err) {
      setSettingsMsg({
        tone: "err",
        text: err instanceof ApiError ? err.message : "Failed to save settings.",
      });
    } finally {
      setSettingsBusy(false);
    }
  };

  const setSettingField = (field: keyof ApprovalSettings, value: string) =>
    setSettings((prev) => (prev ? { ...prev, [field]: value === "" ? NaN : Number(value) } : prev));

  const inputCls =
    "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none";
  const btnCls =
    "rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-60";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Admin</h1>
        <p className="text-sm text-slate-500">
          Configure approval settings, and manage Knowledge Base documents and sample matching data.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card
          title="Approval settings"
          description="Thresholds and three-way match margins used to auto-approve or escalate invoices."
        >
          {settingsLoading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : settings ? (
            <div className="space-y-2">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Amount Auto-Approval Threshold (NZD)</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className={inputCls}
                  value={Number.isNaN(settings.amountThreshold) ? "" : settings.amountThreshold}
                  onChange={(e) => setSettingField("amountThreshold", e.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">
                  Ouput Confidence Threshold (0–1, e.g. 0.85 = 85%)
                </span>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  className={inputCls}
                  value={Number.isNaN(settings.confidenceThreshold) ? "" : settings.confidenceThreshold}
                  onChange={(e) => setSettingField("confidenceThreshold", e.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">
                  Total Amount Tolerance (0–1, 0 = exact, 0.02 = ±2%)
                </span>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  className={inputCls}
                  value={Number.isNaN(settings.poAmountTolerance) ? "" : settings.poAmountTolerance}
                  onChange={(e) => setSettingField("poAmountTolerance", e.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">
                  Total Quantity Tolerance (0–1, 0 = exact, 0.02 = ±2%)
                </span>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  className={inputCls}
                  value={Number.isNaN(settings.grQtyTolerance) ? "" : settings.grQtyTolerance}
                  onChange={(e) => setSettingField("grQtyTolerance", e.target.value)}
                />
              </label>
              <button type="button" disabled={settingsBusy} onClick={() => void submitSettings()} className={btnCls}>
                {settingsBusy ? "Saving…" : "Save approval settings"}
              </button>
              <FeedbackLine feedback={settingsMsg} />
            </div>
          ) : (
            <FeedbackLine feedback={settingsMsg} />
          )}
        </Card>

        <Card title="Upload document" description="Add a policy, contract, or record to the Knowledge Base.">
          <DocumentUpload />
        </Card>

        <Card title="Knowledge Base sync" description="Ingest newly uploaded documents so they become searchable.">
          <button type="button" disabled={syncing} onClick={() => void runSync()} className={btnCls}>
            {syncing ? "Starting sync…" : "Trigger KB sync"}
          </button>
          <FeedbackLine feedback={syncMsg} />
        </Card>

        <Card title="Seed sample data" description="Load sample Purchase Orders and Goods Receipts for demos.">
          <button type="button" disabled={seeding} onClick={() => void runSeed()} className={btnCls}>
            {seeding ? "Seeding…" : "Load sample PO/GR data"}
          </button>
          <FeedbackLine feedback={seedMsg} />
        </Card>

        <Card title="Upload purchase order" description="Store a structured PO for three-way matching.">
          <ExtractUpload
            heading="Upload a PO document to auto-fill the fields — or enter them manually below."
            busy={poExtracting}
            fileName={poFileName}
            onFile={(f) => void extractPo(f)}
          />
          <fieldset disabled={poLocked} className="space-y-2 disabled:opacity-60">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Purchase Order Number</span>
              <input
                className={inputCls}
                value={po.poNumber}
                onChange={(e) => setPo({ ...po, poNumber: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Vendor Name</span>
              <input
                className={inputCls}
                value={po.vendorName}
                onChange={(e) => setPo({ ...po, vendorName: e.target.value })}
              />
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
            <button type="button" disabled={poLocked} onClick={() => void submitPo()} className={`${btnCls} inline-flex items-center gap-2`}>
              {poBusy && <Spinner className="text-white" />}
              {poBusy ? "Saving…" : "Save purchase order"}
            </button>
          </fieldset>
          <FeedbackLine feedback={poMsg} />
        </Card>

        <Card title="Upload goods receipt" description="Link a GR to an existing PO for three-way matching.">
          <ExtractUpload
            heading="Upload a GR document to auto-fill the fields — or enter them manually below."
            busy={grExtracting}
            fileName={grFileName}
            onFile={(f) => void extractGr(f)}
          />
          <fieldset disabled={grLocked} className="space-y-2 disabled:opacity-60">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Goods Receipt Number/ID</span>
              <input
                className={inputCls}
                value={gr.grId}
                onChange={(e) => setGr({ ...gr, grId: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Purchase Order Number</span>
              <input
                className={inputCls}
                value={gr.poNumber}
                onChange={(e) => setGr({ ...gr, poNumber: e.target.value })}
              />
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
            <button type="button" disabled={grLocked} onClick={() => void submitGr()} className={`${btnCls} inline-flex items-center gap-2`}>
              {grBusy && <Spinner className="text-white" />}
              {grBusy ? "Saving…" : "Save goods receipt"}
            </button>
          </fieldset>
          <FeedbackLine feedback={grMsg} />
        </Card>
      </div>
    </div>
  );
}
