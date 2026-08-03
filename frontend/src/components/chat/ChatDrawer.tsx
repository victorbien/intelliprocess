/**
 * Right-anchored slide-in drawer that wraps the ChatWindow.
 *
 * Dragging:
 *   The header acts as a drag handle. Pointer events move the drawer by
 *   adjusting a (dx, dy) offset applied via CSS transform on top of the
 *   default fixed bottom-0 right-0 anchor.
 *
 *   At rest:  transform = translateX(0) translateX(0)  ← default position
 *   Dragged:  transform = translate(dx px, dy px)
 *
 *   dx is always ≤ 0  (moving left from right edge)
 *   dy is always ≤ 0  (moving up from bottom edge)
 *
 *   The drawer is clamped so every edge stays inside the viewport.
 *
 * Double-clicking the header resets to the default position.
 * Escape and the X button close the drawer; all other behaviour is unchanged.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import ChatWindow from "./ChatWindow";

interface ChatDrawerProps {
  open: boolean;
  onClose: () => void;
}

const DRAWER_WIDTH = 400;   // px — must match the w-[400px] class
const HEADER_HEIGHT = 73;   // px — approximate; used only for clamping

export default function ChatDrawer({ open, onClose }: ChatDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  // (dx, dy) offset in px relative to the default bottom-right anchor.
  // Both are ≤ 0: negative dx moves left, negative dy moves up.
  const [offset, setOffset] = useState({ dx: 0, dy: 0 });

  // Drag state kept in a ref so pointer-move handlers never go stale without
  // needing to be re-registered.
  const drag = useRef<{
    active: boolean;
    startX: number;   // pointer position at drag start
    startY: number;
    originDx: number; // offset at drag start
    originDy: number;
  }>({ active: false, startX: 0, startY: 0, originDx: 0, originDy: 0 });

  // ── Close on Escape ────────────────────────────────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // ── Focus drawer when it opens ────────────────────────────────────────────
  useEffect(() => {
    if (open) {
      const id = setTimeout(() => drawerRef.current?.focus(), 50);
      return () => clearTimeout(id);
    }
  }, [open]);

  // ── Clamping helper ───────────────────────────────────────────────────────
  const clamp = useCallback((dx: number, dy: number) => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // Drawer occupies [vw + dx - DRAWER_WIDTH … vw + dx] horizontally
    // and [vh + dy - drawerHeight … vh + dy] vertically.
    const drawerHeight = drawerRef.current?.offsetHeight ?? vh - 64;

    // Left edge must stay ≥ 0  →  vw + dx - DRAWER_WIDTH ≥ 0  →  dx ≥ DRAWER_WIDTH - vw
    const minDx = DRAWER_WIDTH - vw;
    // Right edge must stay ≤ vw  →  vw + dx ≤ vw  →  dx ≤ 0
    const maxDx = 0;

    // Top edge must stay ≥ 0  →  vh + dy - drawerHeight ≥ 0  →  dy ≥ drawerHeight - vh
    const minDy = HEADER_HEIGHT - vh;   // allow scrolling up so at least the header is visible
    // Bottom edge must stay ≤ vh  →  vh + dy ≤ vh  →  dy ≤ 0
    const maxDy = 0;

    return {
      dx: Math.min(maxDx, Math.max(minDx, dx)),
      dy: Math.min(maxDy, Math.max(minDy, dy)),
    };
  }, []);

  // ── Pointer event handlers ────────────────────────────────────────────────
  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>) {
    // Only react to primary button; ignore if target is a button
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("button")) return;

    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      originDx: offset.dx,
      originDy: offset.dy,
    };
  }

  function handlePointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag.current.active) return;

    const rawDx = drag.current.originDx + (e.clientX - drag.current.startX);
    const rawDy = drag.current.originDy + (e.clientY - drag.current.startY);
    setOffset(clamp(rawDx, rawDy));
  }

  function handlePointerUp(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag.current.active) return;
    drag.current.active = false;
    e.currentTarget.releasePointerCapture(e.pointerId);
  }

  function handleDoubleClick() {
    setOffset({ dx: 0, dy: 0 });
  }

  // ── Build the transform string ────────────────────────────────────────────
  // The inline style owns the full transform so it can't be overridden by
  // Tailwind classes. When closed we bake the slide-out (100% width) into the
  // transform directly; when open we apply only the drag offset.
  const slideX = open ? offset.dx : DRAWER_WIDTH;
  const drawerStyle: React.CSSProperties = {
    transform: `translate(${slideX}px, ${offset.dy}px)`,
  };

  // When the drawer is closed the Tailwind slide-out wins because we set
  // translate-x-full, which overrides the inline transform. Reset offset so
  // re-opening always starts at the default position.
  useEffect(() => {
    if (!open) setOffset({ dx: 0, dy: 0 });
  }, [open]);

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/10 transition-opacity duration-300 ${
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        style={drawerStyle}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Records Assistant"
        className={`fixed bottom-0 right-0 z-50 flex h-[calc(100vh-4rem)] w-[400px] max-w-[calc(100vw-1rem)] flex-col rounded-tl-2xl rounded-tr-2xl bg-white shadow-2xl outline-none
          ${drag.current.active ? "" : "transition-transform duration-300 ease-in-out"}`}
      >
        {/* ── Header / drag handle ─────────────────────────────────── */}
        <div
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onDoubleClick={handleDoubleClick}
          className={`flex items-center justify-between border-b border-gray-200 px-5 py-4 shrink-0 select-none rounded-tl-2xl rounded-tr-2xl
            ${open ? "cursor-grab active:cursor-grabbing" : ""}`}
          title="Drag to move · Double-click to reset"
        >
          <div className="flex items-center gap-3">
            {/* Drag grip dots */}
            <div
              aria-hidden="true"
              className="flex flex-col gap-[3px] mr-1 opacity-30"
            >
              {[0, 1, 2].map((row) => (
                <div key={row} className="flex gap-[3px]">
                  <span className="h-1 w-1 rounded-full bg-gray-500" />
                  <span className="h-1 w-1 rounded-full bg-gray-500" />
                </div>
              ))}
            </div>

            {/* Assistant avatar */}
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-600">
              <svg
                className="h-5 w-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.8}
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                />
              </svg>
            </div>

            <div>
              <h2 className="text-sm font-semibold text-gray-900 leading-tight">
                Records Assistant
              </h2>
              <p className="text-xs text-gray-500">
                Ask about invoices, policies &amp; more
              </p>
            </div>
          </div>

          {/* Close button — stopPropagation so a click here doesn't start a drag */}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            aria-label="Close assistant"
            className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* ── Chat window ──────────────────────────────────────────── */}
        <div className="flex-1 overflow-hidden">
          <ChatWindow />
        </div>
      </div>
    </>
  );
}
