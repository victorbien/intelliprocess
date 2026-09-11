import { WorkflowDiagram } from '../../components/visuals/WorkflowDiagram';

export function HowItWorksPage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">How it works</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Invoice intake to decision support, without the manual bottleneck.
        </h2>
        <WorkflowDiagram />
      </div>
    </div>
  );
}
