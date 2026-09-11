interface MetricCardProps {
  label: string;
  value: string;
  accent?: string;
}

export function MetricCard({ label, value, accent = 'text-brand-200' }: MetricCardProps) {
  return (
    <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5 shadow-glow">
      <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">{label}</p>
      <div className={`mt-4 text-4xl font-semibold ${accent}`}>{value}</div>
    </div>
  );
}
