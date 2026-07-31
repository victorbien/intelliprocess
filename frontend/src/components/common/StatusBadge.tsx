const COLOURS: Record<string, string> = {
  UPLOADED:   "bg-blue-100 text-blue-800",
  PROCESSING: "bg-yellow-100 text-yellow-800",
  EXTRACTED:  "bg-yellow-100 text-yellow-800",
  APPROVED:   "bg-green-100 text-green-800",
  ESCALATED:  "bg-orange-100 text-orange-800",
  REJECTED:   "bg-red-100 text-red-800",
  ERROR:      "bg-red-100 text-red-800",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = COLOURS[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {status}
    </span>
  );
}
