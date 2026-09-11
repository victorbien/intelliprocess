export function PlatformPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">One platform</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          One intelligent platform for operations and organisational insight.
        </h2>

        <div className="mt-12 grid gap-8 lg:grid-cols-2">
          <div className="rounded-[28px] border border-brand-400/35 bg-brand-500/10 p-8 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.28em] text-brand-100">AP automation</p>
            <ul className="mt-6 space-y-4 text-lg text-brand-50">
              <li>• Invoice ingestion and extraction</li>
              <li>• Automated three-way matching</li>
              <li>• Approval or escalation decisions</li>
              <li>• AP dashboard and operational visibility</li>
            </ul>
          </div>

          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-8 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Records intelligence</p>
            <ul className="mt-6 space-y-4 text-lg text-slate-200">
              <li>• Natural language record search</li>
              <li>• Source-backed answers</li>
              <li>• Policy and agreement retrieval</li>
              <li>• Document awareness across organisational records</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
