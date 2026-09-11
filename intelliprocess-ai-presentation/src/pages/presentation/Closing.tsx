export function ClosingPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-5xl text-center">
        <div className="mb-8 text-[10px] uppercase tracking-[0.32em] text-brand-200">Closing</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-7xl">
          IntelliProcess AI
        </h2>
        <p className="mt-8 text-2xl font-medium text-slate-200 md:text-4xl">
          Turning documents into decisions.
          <br />
          Turning records into answers.
        </p>
        <div className="mt-8 rounded-full border border-brand-400/40 bg-brand-500/10 px-6 py-3 text-[10px] uppercase tracking-[0.3em] text-brand-100">
          AI-powered AP automation + intelligent organisational records retrieval
        </div>
      </div>
    </div>
  );
}
