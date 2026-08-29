import { describe, it, expect, beforeEach } from "vitest";

import { clearChat, loadChat, saveChat } from "./storage";
import type { ChatMessage } from "./types";

const sample: ChatMessage[] = [
  { id: "1", role: "user", content: "hi", timestamp: "2026-01-01T00:00:00Z" },
  { id: "2", role: "assistant", content: "hello", timestamp: "2026-01-01T00:00:01Z" },
];

describe("chat storage", () => {
  beforeEach(() => sessionStorage.clear());

  it("returns an empty conversation when nothing is stored", () => {
    expect(loadChat()).toEqual({ messages: [] });
  });

  it("round-trips messages and sessionId (survives reload)", () => {
    saveChat({ sessionId: "sess-1", messages: sample });
    const restored = loadChat();
    expect(restored.sessionId).toBe("sess-1");
    expect(restored.messages).toHaveLength(2);
    expect(restored.messages[1].content).toBe("hello");
  });

  it("clears the conversation", () => {
    saveChat({ sessionId: "sess-1", messages: sample });
    clearChat();
    expect(loadChat()).toEqual({ messages: [] });
  });

  it("recovers gracefully from corrupted storage", () => {
    sessionStorage.setItem("intelliprocess.chat", "{not json");
    expect(loadChat()).toEqual({ messages: [] });
  });
});
