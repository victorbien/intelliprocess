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

import { useEffect, useState, type ReactNode } from "react";

import DocumentUpload from "@/components/admin/DocumentUpload";
import { adminApi, documentsApi } from "@/services/api";
import { ApiError, type ApprovalSettings } from "@/services/types";
import { logger } from "@/services/logger";

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
  const [po, setPo] = useState({ poNumber: "", vendorName: "", totalAmount: "" });
  const [poBusy, setPoBusy] = useState(false);
  const [poMsg, setPoMsg] = useState<Feedback>(null);

  const submitPo = async () => {
    const amount = Number(po.totalAmount);
    if (!po.poNumber.trim() || !po.vendorName.trim() || !Number.isFinite(amount) || amount <= 0) {
      setPoMsg({ tone: "err", text: "PO number, vendor, and a positive amount are required." });
      return;
    }
    setPoBusy(true);
    setPoMsg(null);
    try {
      await adminApi.uploadPurchaseOrder({
        poNumber: po.poNumber.trim(),
        vendorName: po.vendorName.trim(),
        totalAmount: amount,
      });
      setPoMsg({ tone: "ok", text: `Purchase order ${po.poNumber.trim()} stored.` });
      setPo({ poNumber: "", vendorName: "", totalAmount: "" });
    } catch (err) {
      setPoMsg({ tone: "err", text: err instanceof ApiError ? err.message : "PO upload failed." });
    } finally {
      setPoBusy(false);
    }
  };

  // ── GR upload ────────────────────────────────────────────────────────────────
  const [gr, setGr] = useState({ grId: "", poNumber: "", totalQuantityReceived: "" });
  const [grBusy, setGrBusy] = useState(false);
  const [grMsg, setGrMsg] = useState<Feedback>(null);

  const submitGr = async () => {
    const qty = Number(gr.totalQuantityReceived);
    if (!gr.grId.trim() || !gr.poNumber.trim() || !Number.isFinite(qty) || qty <= 0) {
      setGrMsg({ tone: "err", text: "GR id, PO number, and a positive quantity are required." });
      return;
    }
    setGrBusy(true);
    setGrMsg(null);
    try {
      await adminApi.uploadGoodsReceipt({
        grId: gr.grId.trim(),
        poNumber: gr.poNumber.trim(),
        totalQuantityReceived: qty,
      });
      setGrMsg({ tone: "ok", text: `Goods receipt ${gr.grId.trim()} linked to ${gr.poNumber.trim()}.` });
      setGr({ grId: "", poNumber: "", totalQuantityReceived: "" });
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
      ["Confidence threshold", confidenceThreshold],
      ["PO amount tolerance", poAmountTolerance],
      ["GR quantity tolerance", grQtyTolerance],
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
                <span className="text-xs font-medium text-slate-600">Amount auto-approval threshold (USD)</span>
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
                  Confidence threshold (0–1, e.g. 0.85 = 85%)
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
                  PO amount tolerance (0–1, 0 = exact, 0.02 = ±2%)
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
                  GR quantity tolerance (0–1, 0 = exact, 0.02 = ±2%)
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
          <div className="space-y-2">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">PO number</span>
              <input
                className={inputCls}
                value={po.poNumber}
                onChange={(e) => setPo({ ...po, poNumber: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Vendor name</span>
              <input
                className={inputCls}
                value={po.vendorName}
                onChange={(e) => setPo({ ...po, vendorName: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Total amount (USD)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                className={inputCls}
                value={po.totalAmount}
                onChange={(e) => setPo({ ...po, totalAmount: e.target.value })}
              />
            </label>
            <button type="button" disabled={poBusy} onClick={() => void submitPo()} className={btnCls}>
              {poBusy ? "Saving…" : "Save purchase order"}
            </button>
            <FeedbackLine feedback={poMsg} />
          </div>
        </Card>

        <Card title="Upload goods receipt" description="Link a GR to an existing PO for three-way matching.">
          <div className="space-y-2">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">GR id</span>
              <input
                className={inputCls}
                value={gr.grId}
                onChange={(e) => setGr({ ...gr, grId: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">PO number</span>
              <input
                className={inputCls}
                value={gr.poNumber}
                onChange={(e) => setGr({ ...gr, poNumber: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Quantity received</span>
              <input
                type="number"
                min="0"
                step="1"
                className={inputCls}
                value={gr.totalQuantityReceived}
                onChange={(e) => setGr({ ...gr, totalQuantityReceived: e.target.value })}
              />
            </label>
            <button type="button" disabled={grBusy} onClick={() => void submitGr()} className={btnCls}>
              {grBusy ? "Saving…" : "Save goods receipt"}
            </button>
            <FeedbackLine feedback={grMsg} />
          </div>
        </Card>
      </div>
    </div>
  );
}
