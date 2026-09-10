/**
 * Renders extracted invoice fields without confidence badges.
 *
 * The extraction payload is loosely typed (backend returns a free-form dict),
 * so values are rendered defensively. Monetary fields are formatted as
 * currency and line-item amounts are right-aligned for scannability.
 */

interface ExtractionViewProps {
  extraction?: Record<string, unknown> | null;
}

// Fields rendered as labelled key/value pairs, in display order.
const FIELD_ORDER: { key: string; label: string; type: "text" | "date" | "money" }[] = [
  { key: "vendorName", label: "Vendor", type: "text" },
  { key: "invoiceNumber", label: "Invoice #", type: "text" },
  { key: "invoiceDate", label: "Invoice date", type: "date" },
  { key: "dueDate", label: "Due date", type: "date" },
  { key: "poReference", label: "PO reference", type: "text" },
  { key: "paymentTerms", label: "Payment terms", type: "text" },
];

// Monetary summary fields, shown grouped in their own block.
const MONEY_ORDER: { key: string; label: string; emphasize?: boolean }[] = [
  { key: "subtotal", label: "Subtotal" },
  { key: "taxAmount", label: "Tax" },
  { key: "totalAmount", label: "Total", emphasize: true },
];

const _currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

function formatMoney(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  if (value == null || value === "" || Number.isNaN(n)) return "—";
  return _currency.format(n);
}

function formatDate(value: unknown): string {
  if (value == null || value === "") return "—";
  const raw = String(value);
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw; // keep original if unparseable
  return d.toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" });
}

function formatText(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return "—";
}

function formatQty(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  if (value == null || value === "" || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US").format(n);
}

/** A stacked label-over-value field. */
function Field({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="py-1.5">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-800">{value}</dd>
    </div>
  );
}

export default function ExtractionView({
  extraction,
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

  const textFields = FIELD_ORDER.filter((f) => f.key in extraction);
  const moneyFields = MONEY_ORDER.filter((f) => f.key in extraction);

  return (
    <div className="space-y-5">
      {/* Key/value details */}
      <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
        {textFields.map((f) => (
          <Field
            key={f.key}
            label={f.label}
            value={f.type === "date" ? formatDate(extraction[f.key]) : formatText(extraction[f.key])}
          />
        ))}
      </dl>

      {/* Monetary summary */}
      {moneyFields.length > 0 && (
        <div className="rounded-md border border-slate-100 bg-slate-50/50">
          <dl className="divide-y divide-slate-100">
            {moneyFields.map((f) => (
              <div key={f.key} className="flex items-center justify-between px-3 py-2">
                <dt
                  className={`text-sm ${
                    f.emphasize ? "font-semibold text-slate-700" : "text-slate-500"
                  }`}
                >
                  {f.label}
                </dt>
                <dd
                  className={`tabular-nums ${
                    f.emphasize
                      ? "text-base font-semibold text-slate-900"
                      : "text-sm font-medium text-slate-700"
                  }`}
                >
                  {formatMoney(extraction[f.key])}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Line items */}
      {lineItems.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Line items
          </h4>
          <div className="overflow-hidden rounded-md border border-slate-100">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2 text-right font-medium">Qty</th>
                  <th className="px-3 py-2 text-right font-medium">Unit price</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {lineItems.map((li, idx) => (
                  <tr key={idx} className="align-top">
                    <td className="px-3 py-2 text-slate-700">{formatText(li.description)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                      {formatQty(li.quantity)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                      {formatMoney(li.unitPrice)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums font-medium text-slate-700">
                      {formatMoney(li.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
