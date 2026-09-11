export function BusinessValuePage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Business value</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Less manual work. More visibility. Better operational decisions.
        </h2>

        <div className="mt-10 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {[
            ['Reduced repetitive manual work', 'Automating invoice intake and validation reduces the time spent on low-value administrative tasks.'],
            ['Shorter processing cycles', 'Structured extraction and matching accelerate the path from receipt to decision.'],
            ['Improved process visibility', 'Dashboards and status tracking make invoice flows easier to monitor and understand.'],
            ['Improved data accuracy', 'Structured extraction and validation reduce manual rekeying and inconsistent records.'],
            ['Faster records retrieval', 'Natural-language search helps teams locate relevant policies, contracts, and documents faster.'],
            ['Clearer exception handling', 'Escalation paths identify where human review is needed without blocking routine approvals.'],
          ].map(([title, text]) => (
            <div key={title} className="rounded-[24px] border border-slate-700 bg-slate-900/70 p-6 shadow-glow">
              <p className="text-[10px] uppercase tracking-[0.28em] text-brand-200">Outcome</p>
              <h3 className="mt-4 text-xl font-semibold text-white">{title}</h3>
              <p className="mt-3 text-base text-slate-300">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
