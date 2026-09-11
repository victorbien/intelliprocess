export function SecurityPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Security & access</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Enforced access, role-aware workflows, and human review.
        </h2>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {[
            ['Authentication', 'Users access the platform through Amazon Cognito-backed authentication.'],
            ['Authorisation', 'Role-based access controls restrict workflows by user type and responsibility.'],
            ['Human oversight', 'Escalations remain in the hands of the finance manager or AP clerk for approval decisions.'],
          ].map(([title, text]) => (
            <div key={title} className="rounded-[24px] border border-slate-700 bg-slate-900/70 p-6 shadow-glow">
              <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">{title}</p>
              <p className="mt-5 text-lg text-slate-200">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
