/**
 * Chat persistence (Req 6 AC-1/6, Req 7 AC-4).
 *
 * Persists the conversation (messages + sessionId) to sessionStorage so the
 * history survives page reloads and drawer close/open within the same browser
 * session. sessionStorage (not localStorage) keeps the scope to the tab/session
 * and clears when the tab closes.
 */

import { logger } from "@/services/logger";
import type { ChatMessage } from "./types";

const STORAGE_KEY = "intelliprocess.chat";

interface PersistedChat {
  sessionId?: string;
  messages: ChatMessage[];
}

export function loadChat(): PersistedChat {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { messages: [] };
    const parsed = JSON.parse(raw) as PersistedChat;
    return {
      sessionId: parsed.sessionId,
      messages: Array.isArray(parsed.messages) ? parsed.messages : [],
    };
  } catch (err) {
    logger.warn("chat", "Failed to restore chat history", err);
    return { messages: [] };
  }
}

export function saveChat(state: PersistedChat): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    // Quota or serialization issues should never break the UI.
    logger.warn("chat", "Failed to persist chat history", err);
  }
}

export function clearChat(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* no-op */
  }
}
