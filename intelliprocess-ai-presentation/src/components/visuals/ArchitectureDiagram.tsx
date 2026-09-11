const blocks = [
  { label: 'Users', tone: 'bg-slate-800' },
  { label: 'React SPA', tone: 'bg-brand-600/80' },
  { label: 'Cognito', tone: 'bg-sky-600/80' },
  { label: 'API Gateway', tone: 'bg-indigo-600/75' },
  { label: 'Lambda', tone: 'bg-violet-600/80' },
  { label: 'S3 + DynamoDB', tone: 'bg-emerald-600/80' },
  { label: 'Bedrock', tone: 'bg-cyan-600/80' },
  { label: 'Knowledge Base', tone: 'bg-teal-600/75' },
];

export function ArchitectureDiagram() {
  return (
    <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {blocks.map((block, index) => (
        <div key={block.label} className="space-y-3">
          <div className={`rounded-2xl border border-white/10 ${block.tone} p-4 text-center text-sm font-medium text-white shadow-lg`}>
            {block.label}
          </div>
          {index < blocks.length - 1 && (
            <div className="flex justify-center text-xl text-slate-400">↓</div>
          )}
        </div>
      ))}
    </div>
  );
}
