/**
 * Manual approve/reject panel for escalated invoices (AC-3.8.2, AC-3.8.3).
 *
 * Only rendered for FINANCE_MANAGER / ADMIN and only when the invoice is
 * ESCALATED. A comment of at least 5 characters is mandatory.
 */

import { useState } from "react";

import { invoicesApi } from "@/services/api";
import { ApiError } from "@/services/types";
import { logger } from "@/services/logger";

interface ApprovalPanelProps {
  documentId: string;
  onDecision: () => void;
}

const MIN_COMMENT = 5;

export default function ApprovalPanel({ documentId, onDecision }: ApprovalPanelProps) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (action: "APPROVE" | "REJECT") => {
    if (comment.trim().length < MIN_COMMENT) {
      setError(`Please enter a comment of at least ${MIN_COMMENT} characters.`);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await invoicesApi.approve(documentId, action, comment.trim());
      logger.info("invoice", `Invoice ${documentId} ${action}`);
      setComment("");
      onDecision();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to submit decision.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <h3 className="text-sm font-semibold text-amber-800">Manual review required</h3>
      <p className="mt-1 text-xs text-amber-700">
        This invoice was escalated. Approve or reject it with a mandatory comment.
      </p>

      <label className="mt-3 block">
        <span className="text-xs font-medium text-slate-600">Comment</span>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
          placeholder="Reason for approval or rejection…"
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </label>

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={submitting}
          onClick={() => void submit("APPROVE")}
          className="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-green-700 disabled:opacity-60"
        >
          Approve
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => void submit("REJECT")}
          className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
        >
          Reject
        </button>
      </div>
    </div>
  );
}
