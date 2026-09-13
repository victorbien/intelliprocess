import { Link } from 'react-router-dom';
import { slides } from '../../data/slides';

interface PresentationControlsProps {
  currentIndex: number;
  onNext: () => void;
  onPrev: () => void;
  onTogglePresentationMode: () => void;
  presentationMode: boolean;
}

export function PresentationControls({
  currentIndex,
  onNext,
  onPrev,
  onTogglePresentationMode,
  presentationMode,
}: PresentationControlsProps) {
  const currentSlide = slides[currentIndex];

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-50 flex items-center justify-between px-8">
      <div className="pointer-events-auto flex gap-2">
        <button
          type="button"
          onClick={onPrev}
          className="rounded-full border border-white/15 bg-slate-950/50 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-200 transition hover:bg-slate-900/70"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          className="rounded-full border border-brand-400/40 bg-brand-500/20 px-4 py-2 text-xs uppercase tracking-[0.2em] text-brand-100 transition hover:bg-brand-500/30"
        >
          Next
        </button>
      </div>

      <div className="pointer-events-auto flex items-center gap-2">
        <Link
          to="/presentation/overview"
          className="rounded-full border border-white/10 bg-slate-950/40 px-3 py-2 text-[10px] uppercase tracking-[0.2em] text-slate-300 transition hover:bg-slate-900/70"
        >
          Overview
        </Link>
        <button
          type="button"
          onClick={onTogglePresentationMode}
          className="rounded-full border border-white/10 bg-slate-950/40 px-3 py-2 text-[10px] uppercase tracking-[0.2em] text-slate-200 transition hover:bg-slate-900/70"
        >
          {presentationMode ? 'Exit' : 'Presentation'}
        </button>
      </div>

      <div className="pointer-events-auto rounded-full border border-white/10 bg-slate-950/40 px-3 py-2 text-[10px] uppercase tracking-[0.25em] text-slate-200">
        {currentSlide?.title ?? 'Slide'}
      </div>
    </div>
  );
}
