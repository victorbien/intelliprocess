import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { slides } from '../data/slides';

export function usePresentationNavigation() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTyping = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      if (isTyping) return;

      const currentIndex = slides.findIndex((slide) => slide.route === location.pathname);
      const isOnPresentationRoute = currentIndex >= 0;
      if (!isOnPresentationRoute) return;

      const prevent = () => {
        event.preventDefault();
      };

      if (event.key === 'ArrowRight' || event.key === 'ArrowDown' || event.key === ' ') {
        prevent();
        const nextIndex = Math.min(currentIndex + 1, slides.length - 1);
        navigate(slides[nextIndex].route, { replace: false });
      }

      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        prevent();
        const prevIndex = Math.max(currentIndex - 1, 0);
        navigate(slides[prevIndex].route, { replace: false });
      }

      if (event.key === 'Home') {
        prevent();
        navigate(slides[0].route);
      }

      if (event.key === 'End') {
        prevent();
        navigate(slides[slides.length - 1].route);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [location.pathname, navigate]);

  return {
    currentIndex: slides.findIndex((slide) => slide.route === location.pathname),
    total: slides.length,
  };
}
