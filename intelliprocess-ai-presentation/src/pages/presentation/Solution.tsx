export function SolutionPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Introducing IntelliProcess AI</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          One platform for intelligent AP operations and organisational knowledge.
        </h2>

        <div className="mt-12 grid gap-8 lg:grid-cols-2">
          <div className="rounded-[28px] border border-brand-400/40 bg-brand-500/10 p-8 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.3em] text-brand-100">Automated Three-Way Matching</p>
            <h3 className="mt-5 text-3xl font-semibold text-white">Invoice, PO, and GR aligned automatically</h3>
            <p className="mt-4 max-w-md text-lg text-brand-50/90">
              The system ingests invoices, extracts structured data, compares it against purchase orders and goods receipts, and routes exceptions for review.
            </p>
          </div>

          <div className="rounded-[28px] border border-slate-700 bg-slate-900/70 p-8 shadow-glow">
            <p className="text-[10px] uppercase tracking-[0.3em] text-slate-400">Ask-Your-Records Assistant</p>
            <h3 className="mt-5 text-3xl font-semibold text-white">Natural language access to organisational records</h3>
            <p className="mt-4 max-w-md text-lg text-slate-200">
              Users can ask questions in plain language and receive source-backed answers using a document knowledge base and retrieval workflow.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
