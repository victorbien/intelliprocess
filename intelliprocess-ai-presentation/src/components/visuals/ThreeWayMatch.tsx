const comparisons = [
  { label: 'Supplier', value: '✓', tone: 'text-emerald-300' },
  { label: 'PO Reference', value: '✓', tone: 'text-emerald-300' },
  { label: 'Quantity', value: '✓', tone: 'text-emerald-300' },
  { label: 'Amount', value: '✓', tone: 'text-emerald-300' },
];

export function ThreeWayMatch() {
  return (
    <div className="mt-10 grid gap-6 lg:grid-cols-3">
      <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5 shadow-glow">
        <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Purchase Order</p>
        <div className="mt-5 space-y-3 text-sm text-slate-200">
          <div className="flex justify-between"><span>PO #</span><span>PO-2048</span></div>
          <div className="flex justify-between"><span>Vendor</span><span>Northwind</span></div>
          <div className="flex justify-between"><span>Total</span><span>$24,500</span></div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5 shadow-glow">
        <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Goods Receipt</p>
        <div className="mt-5 space-y-3 text-sm text-slate-200">
          <div className="flex justify-between"><span>Qty Received</span><span>125</span></div>
          <div className="flex justify-between"><span>Approved</span><span>Yes</span></div>
          <div className="flex justify-between"><span>Location</span><span>Sydney</span></div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5 shadow-glow">
        <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Supplier Invoice</p>
        <div className="mt-5 space-y-3 text-sm text-slate-200">
          <div className="flex justify-between"><span>Invoice #</span><span>INV-0192</span></div>
          <div className="flex justify-between"><span>Vendor</span><span>Northwind</span></div>
          <div className="flex justify-between"><span>Total</span><span>$24,500</span></div>
        </div>
      </div>

      <div className="lg:col-span-3 mt-4 rounded-3xl border border-brand-400/30 bg-brand-500/10 p-5">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-[10px] uppercase tracking-[0.28em] text-brand-100">Validation</p>
          <span className="rounded-full border border-emerald-400/50 bg-emerald-500/15 px-3 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-200">Matched</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {comparisons.map((item) => (
            <div key={item.label} className="rounded-2xl border border-slate-700 bg-slate-950/70 p-3 text-center">
              <div className={`text-3xl font-semibold ${item.tone}`}>{item.value}</div>
              <div className="mt-2 text-[11px] uppercase tracking-[0.2em] text-slate-400">{item.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
