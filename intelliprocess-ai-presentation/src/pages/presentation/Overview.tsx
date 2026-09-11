export function OverviewPage() {
  return (
    <div className="relative z-10 flex min-h-screen flex-col justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-6 flex items-center gap-3 text-[10px] uppercase tracking-[0.32em] text-brand-200">
          <span className="inline-block h-2 w-2 rounded-full bg-brand-400" />
          Presentation Overview
        </div>
        <h1 className="text-5xl font-semibold tracking-tight text-white md:text-7xl">Overview</h1>
        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            'The Problem',
            'The Transformation',
            'How It Works',
            'Three-Way Matching',
            'Dashboard',
            'Ask Your Records',
            'AWS Architecture',
            'Business Value',
          ].map((item, index) => (
            <div key={item} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4 text-sm text-slate-200">
              <div className="mb-2 text-[10px] uppercase tracking-[0.25em] text-slate-400">0{index + 1}</div>
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
