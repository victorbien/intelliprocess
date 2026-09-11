export function CoverPage() {
  return (
    <div className="relative z-10 flex min-h-screen flex-col justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="inline-flex items-center rounded-full border border-brand-400/40 bg-brand-500/10 px-4 py-2 text-[10px] uppercase tracking-[0.3em] text-brand-100">
          AWS-based AI Platform
        </div>
        <h1 className="mt-8 max-w-5xl text-5xl font-semibold tracking-[-0.06em] text-white md:text-7xl lg:text-8xl">
          IntelliProcess AI
        </h1>
        <div className="mt-8 max-w-3xl text-2xl font-medium leading-relaxed text-slate-200 md:text-4xl">
          Intelligent Accounts Payable
          <br />
          &amp; Organisational Records Retrieval
        </div>
        <p className="mt-8 max-w-2xl text-lg text-slate-300 md:text-xl">
          AI-powered. Automated. Human-supervised.
        </p>

        <div className="mt-12 flex flex-wrap gap-6 text-sm text-slate-300">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/60 px-4 py-3">Automated three-way matching</div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/60 px-4 py-3">AP visibility and review</div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/60 px-4 py-3">Ask-your-records assistant</div>
        </div>
      </div>
    </div>
  );
}
