import { useState } from 'react';

const problemSteps = [
  {
    title: 'Invoice arrives',
    summary: 'A supplier sends an invoice by email or PDF.',
    description: 'The invoice enters the workflow as a scattered document, often detached from the PO or goods receipt history.',
    realLife: ['Supplier sends PDF after delivery', 'AP mailbox receives invoice', 'Record is not linked to source data yet'],
  },
  {
    title: 'Manual data entry',
    summary: 'AP staff re-key invoice details into spreadsheets and ERP.',
    description: 'People manually copy line items, partners, amounts, dates, and tax values into multiple systems.',
    realLife: ['Invoice data is retyped by hand', 'Same information appears in Excel and ERP', 'Errors and duplicate effort build up'],
  },
  {
    title: 'PO + GRN checks',
    summary: 'The team cross-checks against purchase orders and receipts.',
    description: 'Matching requires viewing several screens and comparing documents manually to find mismatches.',
    realLife: ['PO is opened in one system', 'GRN is checked in another', 'Missing or inconsistent values trigger review'],
  },
  {
    title: 'Exceptions pile up',
    summary: 'Small mismatches lead to investigation loops.',
    description: 'When text is ambiguous or records are incomplete, the invoice sits in exception queues waiting for human follow-up.',
    realLife: ['Quantity mismatch', 'Vendor name mismatch', 'Late approval causes delayed payment'],
  },
  {
    title: 'Status stays unclear',
    summary: 'Teams cannot see where the invoice is in real time.',
    description: 'Without a single operational view, status tracking depends on email threads and tribal knowledge.',
    realLife: ['Manager asks for status', 'Team checks inboxes manually', 'Payment delays ripple across the month-end close'],
  },
];

export function ProblemPage() {
  const [selectedStep, setSelectedStep] = useState<(typeof problemSteps)[number] | null>(null);

  return (
    <div className="relative z-10 flex min-h-screen items-center justify-center px-8 py-12">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-8 text-[10px] uppercase tracking-[0.28em] text-brand-200">The problem</div>
        <h2 className="max-w-3xl text-4xl font-semibold tracking-[-0.05em] text-white md:text-6xl">
          Accounts Payable shouldn’t be this manual.
        </h2>

        <div className="mt-10 rounded-[32px] border border-slate-700 bg-slate-900/80 p-6 shadow-glow md:p-8">
          <div className="mb-6 flex items-center justify-between gap-4">
            <div className="text-[10px] uppercase tracking-[0.28em] text-slate-400">Manual workflow</div>
            <div className="rounded-full border border-rose-400/30 bg-rose-500/10 px-3 py-1 text-[9px] uppercase tracking-[0.2em] text-rose-200">
              Slow + fragmented
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-5">
            {problemSteps.map((step, index) => (
              <button
                key={step.title}
                type="button"
                onClick={() => setSelectedStep(step)}
                className="relative text-left transition hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-brand-400/60"
              >
                <div className="flex h-full flex-col rounded-2xl border border-slate-700 bg-slate-950/70 p-4 text-center shadow-[0_0_20px_rgba(15,23,42,0.35)]">
                  <div className="mb-4 flex h-10 w-10 items-center justify-center self-center rounded-full border border-brand-300/40 bg-brand-500/10 text-[10px] font-medium uppercase tracking-[0.2em] text-brand-100">
                    {index + 1}
                  </div>
                  <div className="text-base font-medium text-slate-100">{step.title}</div>
                  <div className="mt-2 text-xs text-slate-400">{step.summary}</div>
                  {index < problemSteps.length - 1 && (
                    <div className="mt-4 flex justify-center text-xl text-slate-500">↓</div>
                  )}
                </div>
              </button>
            ))}
          </div>

          <div className="mt-8 rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4 text-base text-slate-200 md:text-lg">
            Click any stage to see how the work actually happens in real operations.
          </div>
        </div>
      </div>

      {selectedStep && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-6 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-[28px] border border-slate-700 bg-slate-900 p-6 shadow-[0_0_45px_rgba(15,23,42,0.8)]">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.24em] text-brand-200">Node detail</div>
                <h3 className="mt-2 text-2xl font-semibold text-white">{selectedStep.title}</h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedStep(null)}
                className="rounded-full border border-slate-600 bg-slate-800 px-2.5 py-1.5 text-[10px] uppercase tracking-[0.2em] text-slate-200"
              >
                Close
              </button>
            </div>

            <p className="text-sm leading-6 text-slate-300">{selectedStep.description}</p>

            <div className="mt-5 rounded-2xl border border-slate-700 bg-slate-950/70 p-4">
              <div className="mb-3 text-[10px] uppercase tracking-[0.24em] text-slate-400">How it looks in real life</div>
              <div className="space-y-2">
                {selectedStep.realLife.map((item) => (
                  <div key={item} className="flex items-start gap-3 rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-slate-200">
                    <span className="mt-1 h-2 w-2 rounded-full bg-rose-400" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
