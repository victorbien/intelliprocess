import { demoWorkflow } from '../../data/demo';

export function WorkflowDiagram() {
  return (
    <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
      {demoWorkflow.map((item, index) => (
        <div key={item.label} className="flex items-center gap-4">
          <div
            className={[
              'flex h-20 w-32 flex-col items-center justify-center rounded-2xl border text-center shadow-lg',
              item.status === 'done' && 'border-emerald-400/50 bg-emerald-500/15 text-emerald-100',
              item.status === 'active' && 'border-brand-400/60 bg-brand-500/20 text-brand-50',
              item.status === 'pending' && 'border-slate-700 bg-slate-900/60 text-slate-400',
            ].join(' ')}
          >
            <span className="text-[10px] uppercase tracking-[0.2em] opacity-75">Step {index + 1}</span>
            <span className="mt-2 font-medium">{item.label}</span>
          </div>
          {index < demoWorkflow.length - 1 && (
            <div className="text-2xl text-slate-500">→</div>
          )}
        </div>
      ))}
    </div>
  );
}
