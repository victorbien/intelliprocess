import { invoiceFields } from '../../data/demo';

export function DocumentProcessingPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">AI document processing</div>
        <h2 className="max-w-4xl text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Unstructured documents become structured operational data.
        </h2>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1.1fr_1.4fr]">
          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-6 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Invoice</p>
            <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-950/80 p-5">
              <p className="text-lg font-semibold text-white">Northwind Supplies</p>
              <p className="mt-2 text-sm text-slate-300">INV-0192 · 15 Aug 2026</p>
              <div className="mt-6 h-32 rounded-2xl border border-dashed border-brand-500/40 bg-brand-500/5" />
            </div>
          </div>

          <div className="rounded-[28px] border border-brand-400/30 bg-brand-500/10 p-6 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.28em] text-brand-100">Structured output</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {invoiceFields.map((field) => (
                <div key={field} className="rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-sm text-slate-200">
                  {field}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
