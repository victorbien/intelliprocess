import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = axios.create({ baseURL: BASE_URL });

/* ── Invoices ─────────────────────────────────────────────── */

export interface UploadUrlResponse {
  documentId: string;
  uploadUrl: { url: string; fields: Record<string, string> };
  expiresIn: number;
}

export interface InvoiceListItem {
  documentId: string;
  fileName: string;
  status: string;
  uploadedAt: string;
  uploadedBy: string;
  vendorName?: string;
  totalAmount?: number;
}

export interface InvoiceDetail extends InvoiceListItem {
  updatedAt?: string;
  documentUrl?: string;
  extraction?: Record<string, unknown>;
  confidence?: Record<string, number>;
  overallConfidence?: number;
  matchResult?: Record<string, unknown>;
  approvalDecision?: Record<string, unknown>;
  errorDetails?: string;
  processingDurationMs?: number;
}

export async function requestInvoiceUploadUrl(
  fileName: string,
  contentType: string
): Promise<UploadUrlResponse> {
  const { data } = await api.post("/invoices/upload", { fileName, contentType });
  return data.data;
}

export async function uploadFileToS3(
  presigned: UploadUrlResponse["uploadUrl"],
  file: File
): Promise<void> {
  const form = new FormData();
  Object.entries(presigned.fields).forEach(([k, v]) => form.append(k, v));
  form.append("file", file);
  // Direct POST to S3 — no auth header
  await axios.post(presigned.url, form);
}

export async function listInvoices(
  status?: string,
  limit = 20
): Promise<{ items: InvoiceListItem[]; count: number; nextKey?: string }> {
  const params: Record<string, string | number> = { limit };
  if (status) params.status = status;
  const { data } = await api.get("/invoices", { params });
  return data.data;
}

export async function getInvoice(documentId: string): Promise<InvoiceDetail> {
  const { data } = await api.get(`/invoices/${documentId}`);
  return data.data;
}

/* ── Documents ────────────────────────────────────────────── */

export interface DocumentListItem {
  documentId: string;
  fileName: string;
  category: string;
  uploadedAt: string;
  description?: string;
  kbSyncStatus?: string;
}

export async function requestDocumentUploadUrl(
  fileName: string,
  contentType: string,
  category: string,
  description?: string
): Promise<{ documentId: string; uploadUrl: UploadUrlResponse["uploadUrl"]; expiresIn: number }> {
  const { data } = await api.post("/documents/upload", {
    fileName,
    contentType,
    category,
    description,
  });
  return data.data;
}

export async function listDocuments(
  category?: string
): Promise<{ items: DocumentListItem[]; count: number }> {
  const params: Record<string, string> = {};
  if (category) params.category = category;
  const { data } = await api.get("/documents", { params });
  return data.data;
}

/* ── Chat / Records Assistant ─────────────────────────────── */

export interface ChatCitation {
  documentName: string;
  documentId: string;
  pageNumber?: number;
  relevanceScore: number;
  snippet: string;
  category?: string;
}

export interface ChatResponseData {
  answer: string;
  citations: ChatCitation[];
  sessionId: string;
  sourceType: "structured_query" | "document_search" | "hybrid";
  dataSnapshot?: Record<string, unknown>;
  unavailable?: boolean;
  responseTimeMs: number;
}

export async function sendChatMessage(
  question: string,
  sessionId?: string
): Promise<ChatResponseData> {
  const body: Record<string, string> = { question };
  if (sessionId) body.sessionId = sessionId;
  const { data } = await api.post("/chat", body);
  // Backend wraps in { status_code, data: {...} }
  return data.data as ChatResponseData;
}

/* ── Chat SSE Streaming ───────────────────────────────────── */

export interface SseTokenEvent {
  type: "token";
  content: string;
}

export interface SseDoneEvent {
  type: "done";
  sessionId: string;
  sourceType: string;
  citations: ChatCitation[];
  dataSnapshot?: Record<string, unknown> | null;
}

export interface SseErrorEvent {
  type: "error";
  message: string;
}

export interface SsePingEvent {
  type: "ping";
}

export type SseEvent = SseTokenEvent | SseDoneEvent | SseErrorEvent | SsePingEvent;

/**
 * Stream a chat message from the backend SSE endpoint (`POST /chat/stream`).
 *
 * Uses `fetch` (not axios) so the response body can be consumed as a
 * `ReadableStream`. Yields typed `SseEvent` objects as they arrive. Malformed
 * data lines are skipped silently. Pass an `AbortSignal` to cancel the stream.
 *
 * `sendChatMessage` (axios) remains available for backward compatibility.
 */
export async function* streamChatMessage(
  question: string,
  sessionId?: string,
  categoryFilter?: string,
  signal?: AbortSignal
): AsyncGenerator<SseEvent> {
  const body: Record<string, string> = { question };
  if (sessionId) body.sessionId = sessionId;
  if (categoryFilter) body.categoryFilter = categoryFilter;

  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      try {
        yield JSON.parse(dataLine.slice(6)) as SseEvent;
      } catch {
        // skip malformed event
      }
    }
  }
}

/* ── Chat Session Summary & Resume ────────────────────────── */

export interface ChatSessionSummaryItem {
  sessionId: string;
  firstMessage: string;
  lastActivity: string;
  messageCount: number;
  summary?: string;
  summaryGeneratedAt?: string;
}

export interface ChatMessageItem {
  role: string;
  content: string;
  timestamp: string;
  citations?: ChatCitation[] | null;
  sourceType?: string | null;
}

export interface ChatSessionDetailData {
  sessionId: string;
  messages: ChatMessageItem[];
}

// POST /chat/sessions/{id}/summary — fire-and-forget on drawer close. Swallows all errors.
export async function summarizeSession(sessionId: string): Promise<void> {
  try {
    await api.post(`/chat/sessions/${sessionId}/summary`);
  } catch {
    // fire-and-forget: a failed summary must never surface to the user
  }
}

// GET /chat/sessions/{id} — full message history for the expander.
export async function getSession(sessionId: string): Promise<ChatSessionDetailData> {
  const { data } = await api.get(`/chat/sessions/${sessionId}`);
  return data.data as ChatSessionDetailData;
}

// GET /chat/sessions — returns most recent session including its stored summary, or null.
export async function getLatestSessionSummary(): Promise<ChatSessionSummaryItem | null> {
  const { data } = await api.get("/chat/sessions", { params: { limit: 1 } });
  const sessions = data.data as ChatSessionSummaryItem[];
  return sessions.length > 0 ? sessions[0] : null;
}
