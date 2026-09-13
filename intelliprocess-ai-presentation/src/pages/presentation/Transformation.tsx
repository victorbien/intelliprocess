const beforeSteps = [
  { title: 'Invoice arrives', detail: 'Scattered PDFs, emails, and attachments' },
  { title: 'Manual capture', detail: 'Teams re-key data by hand and across systems' },
  { title: 'Reconciliation', detail: 'PO, GRN, and invoice validated manually' },
  { title: 'Exception chasing', detail: 'Missing fields trigger long investigation loops' },
  { title: 'Delayed payment', detail: 'Teams lose time without real-time status visibility' },
];

const afterSteps = [
  { title: 'Ingest documents', detail: 'Receives invoices and structured source records' },
  { title: 'AI extraction', detail: 'Reads, classifies, and normalizes key values' },
  { title: 'Auto matching', detail: 'Compares invoice, PO, and GRN in seconds' },
  { title: 'Exception routing', detail: 'Flags only true business exceptions for review' },
  { title: 'Operational visibility', detail: 'Track status, SLA, and approvals in real time' },
];

const sourceLinks = [
  { label: 'UiPath AP automation', href: 'https://www.uipath.com/' },
  { label: 'Microsoft AI in finance', href: 'https://www.microsoft.com/en-us/ai/solutions/finance' },
  { label: 'Deloitte finance transformation', href: 'https://www2.deloitte.com/us/en/insights/topics/financial-services/finance-operations.html' },
];

export function TransformationPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-7xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Transformation</div>
        <h2 className="max-w-4xl text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          From manual processing to intelligent operations.
        </h2>

        <div className="mt-10 grid gap-6 xl:grid-cols-[0.98fr_1.22fr]">
          <div className="rounded-[30px] border border-slate-700 bg-[radial-gradient(circle_at_top,_rgba(51,65,85,0.8),_rgba(15,23,42,0.96)_55%)] p-6 shadow-[0_0_40px_rgba(15,23,42,0.7)]">
            <div className="mb-6 flex items-center justify-between gap-4">
              <h3 className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Before</h3>
              <div className="rounded-full border border-rose-400/50 bg-rose-500/10 px-3 py-1 text-[9px] uppercase tracking-[0.2em] text-rose-200">
                Manual ops
              </div>
            </div>

            <div className="flow-lane flow-lane-before relative pl-10">
              {beforeSteps.map((step, index) => (
                <div key={step.title} className="flow-step relative mb-4 last:mb-0" style={{ animationDelay: `${index * 180}ms` }}>
                  <div className="flow-dot" />
                  <div className="flow-card rounded-2xl border border-slate-700/80 bg-slate-950/80 p-4 shadow-[0_0_20px_rgba(148,163,184,0.08)]">
                    <div className="mb-1 flex items-center justify-between gap-3">
                      <span className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Step {index + 1}</span>
                      <span className="h-2.5 w-2.5 rounded-full bg-rose-400 shadow-[0_0_18px_rgba(251,113,133,0.8)]" />
                    </div>
                    <div className="text-lg font-medium text-slate-100">{step.title}</div>
                    <div className="mt-2 text-sm text-slate-400">{step.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative overflow-hidden rounded-[30px] border border-emerald-400/40 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.28),_rgba(10,31,42,0.95)_52%)] p-6 shadow-[0_0_60px_rgba(16,185,129,0.24)]">
            <div className="absolute -left-8 top-10 h-40 w-40 rounded-full bg-emerald-400/20 blur-3xl" />
            <div className="absolute right-8 top-4 h-28 w-28 rounded-full bg-cyan-400/15 blur-2xl" />
            <div className="relative">
              <div className="mb-6 flex items-center justify-between gap-4">
                <h3 className="text-[10px] uppercase tracking-[0.28em] text-emerald-100">After</h3>
                <div className="rounded-full border border-emerald-300/50 bg-emerald-500/10 px-3 py-1 text-[9px] uppercase tracking-[0.2em] text-emerald-200">
                  AI-led flow
                </div>
              </div>

              <div className="mb-5 flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-300 shadow-[0_0_12px_rgba(110,231,183,0.9)]" />
                <div className="text-[10px] uppercase tracking-[0.24em] text-emerald-100/80">AI decision layer</div>
              </div>

              <div className="flow-lane flow-lane-after relative pl-10">
                {afterSteps.map((step, index) => (
                  <div key={step.title} className="flow-step relative mb-4 last:mb-0" style={{ animationDelay: `${index * 180}ms` }}>
                    <div className="flow-dot" />
                    <div className="flow-card rounded-2xl border border-emerald-400/35 bg-slate-950/75 p-4 shadow-[0_0_28px_rgba(52,211,153,0.12)]">
                      <div className="mb-1 flex items-center justify-between gap-3">
                        <span className="text-[10px] uppercase tracking-[0.24em] text-emerald-200">Step {index + 1}</span>
                        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_18px_rgba(52,211,153,0.8)]" />
                      </div>
                      <div className="text-lg font-medium text-white">{step.title}</div>
                      <div className="mt-2 text-sm text-emerald-50/80">{step.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-[22px] border border-slate-700/80 bg-slate-900/80 p-4 shadow-[0_0_28px_rgba(15,23,42,0.5)] backdrop-blur-sm">
            <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-slate-400">
              <span>Time saved</span>
              <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-0.5 text-[8px] text-slate-300">P80</span>
            </div>
            <div className="text-3xl font-semibold text-white">60–80%</div>
            <div className="mt-2 text-sm text-slate-300">Faster invoice turnaround</div>
            <div className="mt-3 text-[10px] uppercase tracking-[0.18em] text-slate-500">UiPath / Microsoft</div>
          </div>

          <div className="rounded-[22px] border border-slate-700/80 bg-slate-900/80 p-4 shadow-[0_0_28px_rgba(15,23,42,0.5)] backdrop-blur-sm">
            <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-slate-400">
              <span>Cost saved</span>
              <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-0.5 text-[8px] text-slate-300">Ops</span>
            </div>
            <div className="text-3xl font-semibold text-white">30–50%</div>
            <div className="mt-2 text-sm text-slate-300">Lower operational overhead</div>
            <div className="mt-3 text-[10px] uppercase tracking-[0.18em] text-slate-500">Deloitte / finance ops</div>
          </div>

          <div className="rounded-[22px] border border-slate-700/80 bg-slate-900/80 p-4 shadow-[0_0_28px_rgba(15,23,42,0.5)] backdrop-blur-sm">
            <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-slate-400">
              <span>Effort saved</span>
              <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-0.5 text-[8px] text-slate-300">Work</span>
            </div>
            <div className="text-3xl font-semibold text-white">2–4 hrs</div>
            <div className="mt-2 text-sm text-slate-300">Per batch recovered</div>
            <div className="mt-3 text-[10px] uppercase tracking-[0.18em] text-slate-500">Case studies</div>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-brand-400/20 bg-brand-500/5 p-4 text-sm text-brand-50/85">
          <div className="mb-2 flex items-center justify-between gap-4">
            <div className="text-[10px] uppercase tracking-[0.24em] text-brand-100">Benchmark references</div>
            <div className="text-[9px] uppercase tracking-[0.2em] text-slate-400">Directional estimates</div>
          </div>

          <div className="flex flex-wrap gap-2 text-[9px] uppercase tracking-[0.14em] text-brand-100">
            {sourceLinks.map(({ label, href }) => (
              <a
                key={label}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-brand-400/25 bg-slate-950/35 px-2.5 py-1 transition hover:border-brand-300/60 hover:bg-brand-500/10"
              >
                {label}
              </a>
            ))}
          </div>

          <div className="mt-3 text-sm text-brand-50/85">
            Industry benchmark studies consistently show AI-driven AP automation can materially reduce cycle times, operating cost, and manual effort—often by 60–80%, 30–50%, and several hours per batch respectively.
          </div>
        </div>
      </div>
    </div>
  );
}
