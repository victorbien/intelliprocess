import { useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { slides } from '../../data/slides';
import { ProgressIndicator } from './ProgressIndicator';
import { PresentationControls } from './PresentationControls';

export function PresentationShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [presentationMode, setPresentationMode] = useState(false);

  const currentIndex = slides.findIndex((slide) => slide.route === location.pathname);
  const safeIndex = currentIndex >= 0 ? currentIndex : 0;

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPresentationMode(false);
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => undefined);
        }
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, []);

  const goNext = () => {
    const nextIndex = Math.min(safeIndex + 1, slides.length - 1);
    navigate(slides[nextIndex].route);
  };

  const goPrev = () => {
    const prevIndex = Math.max(safeIndex - 1, 0);
    navigate(slides[prevIndex].route);
  };

  const togglePresentationMode = async () => {
    const nextMode = !presentationMode;
    setPresentationMode(nextMode);

    if (nextMode && document.documentElement.requestFullscreen) {
      try {
        await document.documentElement.requestFullscreen();
      } catch {
        // Ignore browser permission failure and keep the app usable.
      }
    }

    if (!nextMode && document.fullscreenElement) {
      document.exitFullscreen().catch(() => undefined);
    }
  };

  return (
    <div className={`relative min-h-screen overflow-x-hidden overflow-y-auto bg-slate-950 text-slate-50 ${presentationMode ? 'presentation-mode' : ''}`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,137,235,0.2),transparent_35%),radial-gradient(circle_at_bottom_right,_rgba(14,165,233,0.14),transparent_30%)]" />
      <ProgressIndicator currentIndex={safeIndex} />
      <Outlet />
      <PresentationControls
        currentIndex={safeIndex}
        onNext={goNext}
        onPrev={goPrev}
        onTogglePresentationMode={togglePresentationMode}
        presentationMode={presentationMode}
      />
    </div>
  );
}
