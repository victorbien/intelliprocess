export function DemoPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Product demonstration</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Now let’s see it in action.
        </h2>

        <div className="mt-10 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {[
            'Launch Product',
            'View AP Dashboard',
            'Process Invoice',
            'Review Exception',
            'Ask Your Records',
            'View Architecture',
            'Open Security View',
            'Return to Overview',
          ].map((item) => (
            <button
              key={item}
              type="button"
              className="rounded-2xl border border-slate-700 bg-slate-900/70 px-5 py-5 text-left text-base text-slate-100 transition hover:border-brand-400/50 hover:bg-slate-800/80"
            >
              {item}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
