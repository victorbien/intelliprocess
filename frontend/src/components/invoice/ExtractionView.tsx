/**
 * Renders extracted invoice fields with per-field confidence (AC-3.1.x).
 *
 * The extraction payload is loosely typed (backend returns a free-form dict),
 * so values are rendered defensively.
 */

interface ExtractionViewProps {
  extraction?: Record<string, unknown> | null;
  confidence?: Record<string, number> | null;
  overallConfidence?: number | null;
}

const FIELD_LABELS: Record<string, string> = {
  vendorName: "Vendor",
  invoiceNumber: "Invoice #",
  invoiceDate: "Invoice date",
  dueDate: "Due date",
  poReference: "PO reference",
  subtotal: "Subtotal",
  taxAmount: "Tax",
  totalAmount: "Total",
  paymentTerms: "Payment terms",
};

function renderValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return "—"; // skip nested objects/arrays here (line items handled separately)
}

function ConfidenceChip({ score }: { score?: number }) {
  if (score == null) return null;
  const pct = Math.round(score * 100);
  const tone =
    score >= 0.9 ? "bg-green-100 text-green-700" : score >= 0.75 ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-700";
  return (
    <span className={`ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium ${tone}`}>
      {pct}%
    </span>
  );
}

export default function ExtractionView({
  extraction,
  confidence,
  overallConfidence,
}: ExtractionViewProps) {
  if (!extraction) {
    return (
      <p className="text-sm text-slate-400">
        Extraction results are not yet available for this invoice.
      </p>
    );
  }

  const lineItems = Array.isArray(extraction.lineItems)
    ? (extraction.lineItems as Record<string, unknown>[])
    : [];

  const scalarFields = Object.keys(FIELD_LABELS).filter((k) => k in extraction);

  return (
    <div className="space-y-4">
      {overallConfidence != null && (
        <p className="text-sm text-slate-500">
          Overall confidence:
          <ConfidenceChip score={overallConfidence} />
        </p>
      )}

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        {scalarFields.map((key) => (
          <div key={key} className="flex items-center justify-between border-b border-slate-50 py-1">
            <dt className="text-sm text-slate-500">{FIELD_LABELS[key]}</dt>
            <dd className="text-sm font-medium text-slate-800">
              {renderValue(extraction[key])}
              <ConfidenceChip score={confidence?.[key]} />
            </dd>
          </div>
        ))}
      </dl>

      {lineItems.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase text-slate-400">Line items</h4>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-400">
              <tr>
                <th className="py-1 font-medium">Description</th>
                <th className="py-1 font-medium">Qty</th>
                <th className="py-1 font-medium">Unit</th>
                <th className="py-1 font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {lineItems.map((li, idx) => (
                <tr key={idx} className="border-t border-slate-50">
                  <td className="py-1 text-slate-700">{renderValue(li.description)}</td>
                  <td className="py-1 text-slate-600">{renderValue(li.quantity)}</td>
                  <td className="py-1 text-slate-600">{renderValue(li.unitPrice)}</td>
                  <td className="py-1 text-slate-600">{renderValue(li.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
