export function TransformationPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Transformation</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          From manual processing to intelligent operations.
        </h2>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-6 shadow-glow">
            <h3 className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Before</h3>
            <div className="mt-6 space-y-4 text-base text-slate-200">
              {['Documents', 'Manual work', 'Manual matching', 'Investigation', 'Limited visibility'].map((item) => (
                <div key={item} className="rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3">{item}</div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-brand-400/30 bg-brand-500/10 p-6 shadow-glow">
            <h3 className="text-[10px] uppercase tracking-[0.28em] text-brand-100">After</h3>
            <div className="mt-6 space-y-4 text-base text-brand-50">
              {['Documents', 'AI extraction', 'Automated matching', 'Exception routing', 'Operational visibility'].map((item) => (
                <div key={item} className="rounded-2xl border border-brand-400/30 bg-slate-950/40 px-4 py-3">{item}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
