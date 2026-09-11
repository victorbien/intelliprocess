import { MetricCard } from '../../components/visuals/MetricCard';

export function DashboardPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">AP operations dashboard</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Visibility across invoice processing and exceptions.
        </h2>

        <div className="mt-8 grid gap-4 md:grid-cols-4">
          <MetricCard label="Processed" value="1,284" accent="text-brand-100" />
          <MetricCard label="Approved" value="92%" accent="text-emerald-200" />
          <MetricCard label="Escalated" value="103" accent="text-amber-200" />
          <MetricCard label="Avg. time" value="2.4d" accent="text-cyan-200" />
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-6 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Processing pipeline</p>
            <div className="mt-6 space-y-4 text-sm text-slate-200">
              {[
                ['Uploaded', '18'],
                ['Processing', '42'],
                ['Extracted', '73'],
                ['Approved', '311'],
                ['Escalated', '24'],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3">
                  <span>{label}</span>
                  <span className="text-brand-100">{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-6 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Status mix</p>
            <div className="mt-6 space-y-4">
              {[
                ['Approved', '58%'],
                ['Pending', '21%'],
                ['Escalated', '15%'],
                ['Rejected', '6%'],
              ].map(([label, value]) => (
                <div key={label} className="space-y-2">
                  <div className="flex justify-between text-sm text-slate-200">
                    <span>{label}</span>
                    <span>{value}</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-800">
                    <div className="h-full rounded-full bg-brand-500" style={{ width: value }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
