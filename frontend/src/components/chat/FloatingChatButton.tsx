/**
 * Circular trigger button fixed to the bottom-right corner of the viewport.
 * Shows a chat-bubble icon; toggles the ChatDrawer open/closed.
 */

interface FloatingChatButtonProps {
  open: boolean;
  onClick: () => void;
}

export default function FloatingChatButton({ open, onClick }: FloatingChatButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={open ? "Close Records Assistant" : "Open Records Assistant"}
      aria-expanded={open}
      className={`fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg transition-all duration-200
        hover:bg-indigo-700 hover:scale-110 hover:shadow-xl
        focus:outline-none focus:ring-4 focus:ring-indigo-300
        active:scale-95
        ${open ? "rotate-90" : "rotate-0"}`}
    >
      {open ? (
        /* X icon when drawer is open */
        <svg
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      ) : (
        /* Chat bubble icon when closed */
        <svg
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
          />
        </svg>
      )}
    </button>
  );
}
