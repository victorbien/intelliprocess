import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getInvoice, type InvoiceDetail } from "../services/api";
import StatusBadge from "../components/common/StatusBadge";

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    getInvoice(id)
      .then(setInvoice)
      .catch((err) => {
        const msg = err?.response?.data?.error ?? "Failed to load invoice.";
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;
  if (error)   return (
    <div className="space-y-3">
      <p className="text-red-500">{error}</p>
      <Link to="/invoices" className="text-blue-600 hover:underline text-sm">← Back to Invoices</Link>
    </div>
  );
  if (!invoice) return null;

  const extraction = invoice.extraction as Record<string, any> | undefined;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Link to="/invoices" className="text-blue-600 hover:underline text-sm">
          ← Back
        </Link>
        <h1 className="text-xl font-bold text-gray-800">{invoice.fileName}</h1>
        <StatusBadge status={invoice.status} />
      </div>

      {/* Metadata */}
      <Section title="Invoice Metadata">
        <Row label="Document ID" value={invoice.documentId} mono />
        <Row label="Status"      value={<StatusBadge status={invoice.status} />} />
        <Row label="Uploaded"    value={new Date(invoice.uploadedAt).toLocaleString()} />
        <Row label="Uploaded by" value={invoice.uploadedBy} />
        {invoice.processingDurationMs != null && (
          <Row label="Processing time" value={`${(invoice.processingDurationMs / 1000).toFixed(1)}s`} />
        )}
        {invoice.errorDetails && (
          <Row label="Error" value={<span className="text-red-500">{invoice.errorDetails}</span>} />
        )}
      </Section>

      {/* Extraction */}
      {extraction && (
        <Section title="Extracted Fields">
          {Object.entries(extraction).map(([field, val]) => {
            if (field === "lineItems") return null;
            const conf = (invoice.confidence as any)?.[field];
            return (
              <Row
                key={field}
                label={camel(field)}
                value={String(val ?? "—")}
                badge={conf != null ? confBadge(conf) : undefined}
              />
            );
          })}

          {extraction.lineItems && Array.isArray(extraction.lineItems) && (
            <div className="col-span-2 mt-2">
              <p className="text-xs text-gray-500 font-medium mb-1">Line Items</p>
              <table className="w-full text-xs border rounded overflow-hidden">
                <thead className="bg-gray-50 text-gray-500">
                  <tr>
                    {["Description","Qty","Unit Price","Amount"].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {extraction.lineItems.map((item: any, i: number) => (
                    <tr key={i}>
                      <td className="px-3 py-2">{item.description}</td>
                      <td className="px-3 py-2">{item.quantity}</td>
                      <td className="px-3 py-2">${item.unitPrice?.toFixed(2)}</td>
                      <td className="px-3 py-2">${item.amount?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}

      {/* Match Result */}
      {invoice.matchResult && (
        <Section title="Match Result">
          <pre className="col-span-2 text-xs bg-gray-50 rounded p-3 overflow-auto">
            {JSON.stringify(invoice.matchResult, null, 2)}
          </pre>
        </Section>
      )}

      {/* Approval Decision */}
      {invoice.approvalDecision && (
        <Section title="Approval Decision">
          <pre className="col-span-2 text-xs bg-gray-50 rounded p-3 overflow-auto">
            {JSON.stringify(invoice.approvalDecision, null, 2)}
          </pre>
        </Section>
      )}

      {/* Document preview link */}
      {invoice.documentUrl && (
        <Section title="Document">
          <a
            href={invoice.documentUrl}
            target="_blank"
            rel="noreferrer"
            className="col-span-2 text-blue-600 underline text-sm"
          >
            Open document ↗
          </a>
        </Section>
      )}
    </div>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────────── */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border rounded-lg shadow-sm p-5">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">{title}</h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2">{children}</dl>
    </div>
  );
}

function Row({
  label,
  value,
  mono = false,
  badge,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  badge?: React.ReactNode;
}) {
  return (
    <>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className={`text-sm text-gray-800 flex items-center gap-2 ${mono ? "font-mono text-xs" : ""}`}>
        {value}
        {badge}
      </dd>
    </>
  );
}

function camel(s: string) {
  return s.replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase());
}

function confBadge(conf: number) {
  const pct = Math.round(conf * 100);
  const cls =
    conf >= 0.85 ? "bg-green-100 text-green-700" :
    conf >= 0.70 ? "bg-yellow-100 text-yellow-700" :
                   "bg-red-100 text-red-700";
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cls}`}>
      {pct}%
    </span>
  );
}
