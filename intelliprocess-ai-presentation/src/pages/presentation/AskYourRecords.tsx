import { AIAssistantCard } from '../../components/visuals/AIAssistantCard';
import { demoRecords } from '../../data/demo';

export function AskYourRecordsPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">Ask Your Records</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Ask a question. Get a source-backed answer.
        </h2>

        <AIAssistantCard />

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {demoRecords.map((record) => (
            <div key={record.title} className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
              <div className="text-[10px] uppercase tracking-[0.25em] text-slate-400">{record.category}</div>
              <h3 className="mt-4 text-lg font-semibold text-white">{record.title}</h3>
              <p className="mt-3 text-sm text-slate-300">{record.excerpt}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
