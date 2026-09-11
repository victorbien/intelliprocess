export function ProblemPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">The problem</div>
        <h2 className="max-w-3xl text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Accounts Payable shouldn’t be this manual.
        </h2>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.7fr_1fr]">
          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-6 shadow-glow">
            <div className="flex flex-col gap-3 text-sm text-slate-200 md:text-base">
              {[
                'Supplier Invoice',
                'Manual Capture',
                'Purchase Order',
                'Goods Receipt',
                'Manual Reconciliation',
                'Exception Investigation',
                'Status Tracking',
              ].map((step, index) => (
                <div key={step} className="flex items-center gap-4">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full border border-brand-300/40 bg-brand-500/10 text-[10px] uppercase tracking-[0.2em] text-brand-100">
                    {index + 1}
                  </div>
                  <div className="flex-1 rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-3">{step}</div>
                  {index < 6 && <span className="text-xl text-slate-500">↓</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4 text-lg text-slate-200">
            {[
              'Manual data entry slows processing.',
              'Reconciliation is repetitive and error-prone.',
              'Exceptions require time-consuming investigation.',
              'Limited visibility makes team coordination harder.',
              'Supporting records are difficult to retrieve quickly.',
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
