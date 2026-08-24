/** UI-side chat message model. */

import type { Citation, ChatSourceType } from "@/services/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citations?: Citation[];
  sourceType?: ChatSourceType;
  dataSnapshot?: Record<string, unknown> | null;
  isError?: boolean;
}
