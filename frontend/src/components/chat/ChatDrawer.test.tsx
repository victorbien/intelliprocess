import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import ChatDrawer from "./ChatDrawer";
import { chatApi } from "@/services/api";

// Mock the API module so no network calls happen.
vi.mock("@/services/api", () => ({
  chatApi: { ask: vi.fn() },
}));

const mockedAsk = vi.mocked(chatApi.ask);

describe("ChatDrawer", () => {
  beforeEach(() => {
    mockedAsk.mockReset();
    // ChatDrawer now restores from sessionStorage; isolate each test.
    sessionStorage.clear();
  });

  it("does not call the API for an empty question (AC-4.1.4)", () => {
    render(<ChatDrawer open onClose={() => {}} />);
    const send = screen.getByRole("button", { name: /send/i });
    // Empty input -> button disabled, and clicking should not call the API.
    expect(send).toBeDisabled();
    fireEvent.click(send);
    expect(mockedAsk).not.toHaveBeenCalled();
  });

  it("sends a question and renders the assistant answer with a citation", async () => {
    mockedAsk.mockResolvedValueOnce({
      answer: "You have 5 escalated invoices.",
      citations: [
        {
          documentName: "Policy.pdf",
          documentId: "doc-1",
          relevanceScore: 0.9,
          snippet: "Escalation rules…",
        },
      ],
      sessionId: "sess-1",
      sourceType: "structured",
      dataSnapshot: { escalated: 5 },
      responseTimeMs: 100,
    });

    render(<ChatDrawer open onClose={() => {}} />);
    const input = screen.getByPlaceholderText(/type your question/i);
    fireEvent.change(input, { target: { value: "How many escalated?" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(mockedAsk).toHaveBeenCalledWith("How many escalated?", undefined, undefined);
    await waitFor(() =>
      expect(screen.getByText("You have 5 escalated invoices.")).toBeInTheDocument(),
    );
    // dataSnapshot value rendered (key "escalated" -> "Escalated", value 5).
    expect(screen.getByText("5")).toBeInTheDocument();
    // A citation source is shown.
    expect(screen.getByText(/Policy\.pdf/)).toBeInTheDocument();
  });

  it("shows an error bubble when the API call fails", async () => {
    mockedAsk.mockRejectedValueOnce(new Error("boom"));

    render(<ChatDrawer open onClose={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/type your question/i), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/assistant is unavailable/i)).toBeInTheDocument(),
    );
  });
});
