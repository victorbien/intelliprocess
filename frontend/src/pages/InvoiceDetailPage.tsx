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
      <div className="flex items-center justify-between">
        <div>
          <Link to="/invoices" className="text-sm text-indigo-600 hover:underline">
            ← Back to invoices
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-slate-800">{invoice.fileName}</h1>
        </div>
        <StatusBadge status={invoice.status} />
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
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Decision</dt>
                  <dd className="font-medium text-slate-800">{decision.decision ?? "—"}</dd>
                </div>
                {decision.approver && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">By</dt>
                    <dd className="text-slate-700">{decision.approver}</dd>
                  </div>
                )}
                {decision.reason && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Reason</dt>
                    <dd className="text-slate-700">{decision.reason}</dd>
                  </div>
                )}
                {decision.comment && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Comment</dt>
                    <dd className="text-slate-700">{decision.comment}</dd>
                  </div>
                )}
              </dl>
            </Section>
          )}

          {invoice.documentUrl && (
            <a
              href={invoice.documentUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-block rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-indigo-600 hover:bg-slate-50"
            >
              View original document ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
