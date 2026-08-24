/**
 * Floating chat launcher (Requirement 7 AC 1, 9).
 *
 * Fixed to the bottom-right corner on every route, with a contrasting accent
 * color and drop shadow. Toggles the chat drawer.
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
      className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2"
    >
      {open ? (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      ) : (
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 10h8M8 14h5m-9 6l3.5-2.5A2 2 0 0111 17h6a3 3 0 003-3V7a3 3 0 00-3-3H6a3 3 0 00-3 3v13z"
          />
        </svg>
      )}
    </button>
  );
}
