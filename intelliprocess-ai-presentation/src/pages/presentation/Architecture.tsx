import { ArchitectureDiagram } from '../../components/visuals/ArchitectureDiagram';

export function ArchitecturePage() {
  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">AWS architecture</div>
        <h2 className="text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          A serverless architecture built for AI-powered processing and secure access.
        </h2>

        <ArchitectureDiagram />

        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4 text-sm text-slate-200">
          {[
            'React + TypeScript',
            'Amazon Cognito',
            'API Gateway',
            'AWS Lambda',
            'Amazon S3',
            'Amazon DynamoDB',
            'Amazon Bedrock',
            'Bedrock Knowledge Bases',
          ].map((item) => (
            <div key={item} className="rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-3">{item}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
