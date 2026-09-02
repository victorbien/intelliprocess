/** Invoice detail page (task 5.3): extraction, matching, and manual review. */

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import StatusBadge from "@/components/common/StatusBadge";
import Spinner from "@/components/common/Spinner";
import ErrorAlert from "@/components/common/ErrorAlert";
import ExtractionView from "@/components/invoice/ExtractionView";
import MatchingResult from "@/components/invoice/MatchingResult";
import ApprovalPanel from "@/components/invoice/ApprovalPanel";
import { useAuth } from "@/context/useAuth";
import { invoicesApi } from "@/services/api";
import { ApiError, type InvoiceDetail } from "@/services/types";
import { logger } from "@/services/logger";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-700">{title}</h2>
      {children}
    </section>
  );
}

function humanizeRole(role?: string): string {
  const map: Record<string, string> = {
    AP_CLERK: "AP Clerk",
    FINANCE_MANAGER: "Finance Manager",
    ADMIN: "Administrator",
    STAFF: "Staff",
  };
  return map[String(role ?? "")] ?? String(role ?? "—");
}

function formatDateTime(value?: string): string {
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

/** Coloured pill for the automated/manual approval decision. */
function DecisionBadge({ decision }: { decision?: string }) {
  const d = String(decision ?? "").toUpperCase();
  const label =
    d === "APPROVE" || d === "APPROVED"
      ? "Approved"
      : d === "REJECT" || d === "REJECTED"
        ? "Rejected"
        : d === "ESCALATE" || d === "ESCALATED"
          ? "Escalated"
          : decision || "—";
  const tone =
    d.startsWith("APPROV")
      ? "bg-green-100 text-green-700"
      : d.startsWith("REJECT")
        ? "bg-red-100 text-red-700"
        : "bg-amber-100 text-amber-800";
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>{label}</span>;
}

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasRole } = useAuth();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await invoicesApi.detail(id);
      setInvoice(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to load invoice.";
      logger.error("invoice", "Detail load failed", err);
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
        <Spinner label="Loading invoice" />
      </div>
    );
  }

  if (error || !invoice) {
    return <ErrorAlert message={error ?? "Invoice not found."} onRetry={() => void load()} />;
  }

  const canReview = hasRole("FINANCE_MANAGER", "ADMIN") && invoice.status === "ESCALATED";
  const decision = invoice.approvalDecision;

  return (
    <div className="space-y-4">
      <div>
        <Link to="/invoices" className="text-sm text-indigo-600 hover:underline">
          ← Back to invoices
        </Link>
        <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="break-words text-xl font-semibold text-slate-800">{invoice.fileName}</h1>
            <p className="mt-1 text-xs text-slate-400">
              Uploaded by {invoice.uploadedBy}
              {invoice.uploadedAt && <> · {formatDateTime(invoice.uploadedAt)}</>}
            </p>
          </div>
          <StatusBadge status={invoice.status} />
        </div>
      </div>

      {invoice.errorDetails && (
        <ErrorAlert message={`Processing error: ${invoice.errorDetails}`} />
      )}

      {canReview && <ApprovalPanel documentId={invoice.documentId} onDecision={() => void load()} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section title="Extracted data">
          <ExtractionView
            extraction={invoice.extraction}
            confidence={invoice.confidence}
            overallConfidence={invoice.overallConfidence}
          />
        </Section>

        <div className="space-y-4">
          <Section title="Matching">
            <MatchingResult matchResult={invoice.matchResult} />
          </Section>

          {decision && (
            <Section title="Approval decision">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <DecisionBadge decision={decision.decision} />
                  {decision.escalateTo && (
                    <span className="text-xs text-slate-500">
                      to <span className="font-medium text-slate-700">{humanizeRole(decision.escalateTo)}</span>
                    </span>
                  )}
                </div>

                <dl className="space-y-2 text-sm">
                  {decision.reason && (
                    <div>
                      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">Reason</dt>
                      <dd className="mt-0.5 text-slate-700">{decision.reason}</dd>
                    </div>
                  )}
                  {decision.comment && (
                    <div>
                      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">Comment</dt>
                      <dd className="mt-0.5 text-slate-700">{decision.comment}</dd>
                    </div>
                  )}
                  {(decision.approver || decision.approvedAt) && (
                    <div>
                      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
                        Reviewed by
                      </dt>
                      <dd className="mt-0.5 text-slate-700">
                        {decision.approver ?? "—"}
                        {decision.approvedAt && (
                          <span className="text-slate-400"> · {formatDateTime(decision.approvedAt)}</span>
                        )}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            </Section>
          )}

          {invoice.documentUrl && (
            <a
              href={invoice.documentUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-indigo-600 transition hover:bg-slate-50"
            >
              View original document
              <span aria-hidden>↗</span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
