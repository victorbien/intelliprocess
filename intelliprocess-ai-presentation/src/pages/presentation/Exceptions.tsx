export function ExceptionsPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Human review</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          AI automates the routine. People handle the exceptions.
        </h2>

        <div className="mt-10 grid gap-8 lg:grid-cols-2">
          <div className="rounded-[28px] border border-brand-400/35 bg-brand-500/10 p-7 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.32em] text-brand-100">Decision flow</p>
            <div className="mt-8 space-y-4 text-lg text-brand-50">
              <div className="rounded-2xl border border-brand-300/30 bg-slate-950/30 p-4">AI processing</div>
              <div className="flex justify-center text-2xl text-brand-200">↓</div>
              <div className="rounded-2xl border border-brand-300/30 bg-slate-950/30 p-4">Match check</div>
              <div className="flex justify-center gap-6 text-sm text-slate-300">
                <span className="rounded-full border border-emerald-400/50 bg-emerald-500/15 px-4 py-2 text-emerald-100">Pass</span>
                <span className="rounded-full border border-amber-400/50 bg-amber-500/15 px-4 py-2 text-amber-100">Fail</span>
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-7 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.32em] text-slate-400">Escalation model</p>
            <div className="mt-8 space-y-4 text-base text-slate-200">
              <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">Amount threshold exceeded → Finance Manager</div>
              <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">Match failure → AP Clerk review</div>
              <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">Low confidence → human validation</div>
              <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">Reason codes and comments retained for traceability</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
