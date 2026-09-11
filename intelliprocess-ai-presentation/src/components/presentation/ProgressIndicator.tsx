import { slides } from '../../data/slides';

export function ProgressIndicator({ currentIndex }: { currentIndex: number }) {
  return (
    <div className="pointer-events-none absolute right-8 top-6 z-20 flex items-center gap-3 rounded-full border border-white/10 bg-slate-950/40 px-3 py-1.5 text-[10px] uppercase tracking-[0.25em] text-slate-200 backdrop-blur-sm">
      <span>{String(currentIndex + 1).padStart(2, '0')}</span>
      <span className="text-slate-500">/</span>
      <span>{String(slides.length).padStart(2, '0')}</span>
    </div>
  );
}
