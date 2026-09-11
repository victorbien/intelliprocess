import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import ChatDrawer from "./ChatDrawer";
import { streamChatMessage, type SseEvent } from "@/services/api";

// Mock the API module so no network calls happen. The chat widget now uses the
// SSE streaming API (`streamChatMessage`, an async generator) instead of the
// legacy non-streaming `chatApi.ask`.
vi.mock("@/services/api", () => ({
  streamChatMessage: vi.fn(),
  // Session resume feature: return null so no resume prompt is shown in tests.
  getLatestSessionSummary: vi.fn(() => Promise.resolve(null)),
  summarizeSession: vi.fn(() => Promise.resolve(null)),
}));

const mockedStream = vi.mocked(streamChatMessage);

// Helper: build an async generator that yields the given SSE events in order.
function makeStream(events: SseEvent[]) {
  return async function* () {
    for (const ev of events) {
      yield ev;
    }
  };
}

describe("ChatDrawer", () => {
  beforeEach(() => {
    mockedStream.mockReset();
    // ChatDrawer restores from sessionStorage; isolate each test.
    sessionStorage.clear();
  });

  it("does not call the API for an empty question (AC-4.1.4)", () => {
    render(<ChatDrawer open onClose={() => {}} />);
    const send = screen.getByRole("button", { name: /send/i });
    // Empty input -> button disabled, and clicking should not call the API.
    expect(send).toBeDisabled();
    fireEvent.click(send);
    expect(mockedStream).not.toHaveBeenCalled();
  });

  it("sends a question and renders the streamed assistant answer with a citation", async () => {
    mockedStream.mockImplementation(
      makeStream([
        { type: "token", content: "You have 5 escalated invoices." },
        {
          type: "done",
          sessionId: "sess-1",
          sourceType: "structured_query",
          citations: [
            {
              documentName: "Policy.pdf",
              documentId: "doc-1",
              relevanceScore: 0.9,
              snippet: "Escalation rules...",
            },
          ],
          dataSnapshot: { escalated: 5 },
        },
      ]) as unknown as typeof streamChatMessage,
    );

    render(<ChatDrawer open onClose={() => {}} />);
    const input = screen.getByPlaceholderText(/ask about/i);
    fireEvent.change(input, { target: { value: "How many escalated?" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(mockedStream).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByText("You have 5 escalated invoices.")).toBeInTheDocument(),
    );
    // A citation source is shown.
    await waitFor(() =>
      expect(screen.getByText(/Policy\.pdf/)).toBeInTheDocument(),
    );
  });

  it("shows an error banner when the stream yields an error event", async () => {
    mockedStream.mockImplementation(
      makeStream([
        { type: "error", message: "The assistant is unavailable right now." },
      ]) as unknown as typeof streamChatMessage,
    );

    render(<ChatDrawer open onClose={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/ask about/i), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/assistant is unavailable/i)).toBeInTheDocument(),
    );
  });
});
