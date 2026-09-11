export function AIAssistantCard() {
  return (
    <div className="mt-8 mx-auto max-w-3xl rounded-[28px] border border-slate-700 bg-slate-900/80 p-6 shadow-glow">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Ask Your Records</p>
          <h3 className="mt-2 text-xl font-semibold text-white">What information is available about Northwind?</h3>
        </div>
        <div className="rounded-full border border-emerald-400/50 bg-emerald-500/15 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-200">Source-backed</div>
      </div>

      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-700 bg-slate-950/70 p-4 text-sm text-slate-200">
          <span className="font-medium text-slate-400">User:</span> “What information do we have about the vendor and related procurement documents?”
        </div>
        <div className="rounded-2xl border border-brand-400/30 bg-brand-500/10 p-4 text-sm text-brand-50">
          <span className="font-medium text-brand-200">AI:</span> The platform can retrieve relevant policy, contract, and procurement records and answer using source citations.
        </div>
        <div className="flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.2em] text-slate-300">
          <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-1">Supplier policy</span>
          <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-1">Procurement agreement</span>
          <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-1">Invoice record</span>
        </div>
      </div>
    </div>
  );
}
