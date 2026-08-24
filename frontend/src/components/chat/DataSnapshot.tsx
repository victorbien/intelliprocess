/**
 * Renders a structured-query dataSnapshot as a compact key/value list
 * (Requirement 7 AC 7).
 */

function formatKey(key: string): string {
  // camelCase / snake_case -> "Title Case"
  return key
    .replace(/[_-]/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function DataSnapshot({ snapshot }: { snapshot: Record<string, unknown> }) {
  const entries = Object.entries(snapshot);
  if (entries.length === 0) return null;

  return (
    <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 rounded-md bg-slate-50 p-2 text-xs">
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="truncate text-slate-500">{formatKey(key)}</dt>
          <dd className="text-right font-medium text-slate-800">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
