/**
 * API client — axios instance with JWT injection, error normalization, and
 * typed methods for every backend endpoint used by the UI.
 *
 * The backend wraps successful responses as { statusCode, data } and errors as
 * { statusCode, error: { code, message } } (older handlers may return a bare
 * string `error`). `unwrap` and `normalizeError` handle both shapes.
 */
import axios, { AxiosError, type AxiosInstance } from "axios";
import { getToken } from "./auth";
import { logger } from "./logger";
import {
  ApiError,
  type ApiSuccess,
  type ChatResponse,
  type DashboardStats,
  type DocumentCategory,
  type DocumentListItem,
  type DocumentUploadResponse,
  type ApprovalSettings,
  type GoodsReceiptUploadResponse,
  type InvoiceApproveResponse,
  type InvoiceDetail,
  type InvoiceListItem,
  type InvoiceUploadResponse,
  type KbSyncResponse,
  type PaginatedResponse,
  type PresignedPost,
  type PurchaseOrderUploadResponse,
  type SeedDataResponse,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 65_000, // Bedrock RAG can take up to ~60s (AC-4.1.1 budget + margin).
});

// Attach the bearer token (when available) to every request.
http.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** Convert an axios error into a normalized ApiError with a friendly message. */
function normalizeError(err: unknown): ApiError {
  if (axios.isAxiosError(err)) {
    const axiosErr = err as AxiosError<{ error?: { code?: string; message?: string } | string }>;
    const status = axiosErr.response?.status ?? 0;
    const body = axiosErr.response?.data;
    let message = "Something went wrong. Please try again.";
    let code = "UNKNOWN";
    if (body && typeof body === "object" && "error" in body) {
      const e = (body as { error?: { code?: string; message?: string } | string }).error;
      if (typeof e === "string") {
        message = e;
      } else if (e) {
        message = e.message ?? message;
        code = e.code ?? code;
      }
    } else if (axiosErr.code === "ECONNABORTED") {
      message = "The request timed out. Please try again.";
      code = "TIMEOUT";
    } else if (status === 0) {
      message = "Unable to reach the server. Check your connection and try again.";
      code = "NETWORK_ERROR";
    }
    logger.error("api", `${axiosErr.config?.method?.toUpperCase()} ${axiosErr.config?.url} -> ${status} ${code}: ${message}`);
    return new ApiError(message, status, code);
  }
  logger.error("api", "Unexpected non-axios error", err);
  return new ApiError("An unexpected error occurred.", 0, "UNKNOWN");
}

/** Extract the `data` payload from the standard success envelope. */
function unwrap<T>(payload: ApiSuccess<T> | T): T {
  if (payload && typeof payload === "object" && "data" in (payload as ApiSuccess<T>)) {
    return (payload as ApiSuccess<T>).data;
  }
  return payload as T;
}

async function get<T>(url: string): Promise<T> {
  try {
    const res = await http.get<ApiSuccess<T>>(url);
    return unwrap<T>(res.data);
  } catch (err) {
    throw normalizeError(err);
  }
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  try {
    const res = await http.post<ApiSuccess<T>>(url, body ?? {});
    return unwrap<T>(res.data);
  } catch (err) {
    throw normalizeError(err);
  }
}

async function put<T>(url: string, body?: unknown): Promise<T> {
  try {
    const res = await http.put<ApiSuccess<T>>(url, body ?? {});
    return unwrap<T>(res.data);
  } catch (err) {
    throw normalizeError(err);
  }
}

// ─── Presigned S3 upload helper ───────────────────────────────────────────────
function buildFormData(fields: Record<string, string>, file: File): FormData {
  const form = new FormData();
  Object.entries(fields).forEach(([k, v]) => form.append(k, v));
  form.append("file", file); // `file` must be the last field for S3 POST.
  return form;
}

/** POST a file directly to S3 using a presigned POST policy. */
export async function uploadToS3(presigned: PresignedPost, file: File): Promise<void> {
  try {
    await axios.post(presigned.url, buildFormData(presigned.fields, file), {
      headers: { "Content-Type": "multipart/form-data" },
    });
  } catch (err) {
    logger.error("api", "Direct S3 upload failed", err);
    throw new ApiError("File upload to storage failed. Please try again.", 0, "UPLOAD_FAILED");
  }
}

// ─── Invoices ─────────────────────────────────────────────────────────────────
export const invoicesApi = {
  requestUpload: (fileName: string, contentType: string) =>
    post<InvoiceUploadResponse>("/invoices/upload", { fileName, contentType }),
  list: (params?: { status?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return get<PaginatedResponse<InvoiceListItem>>(`/invoices${qs ? `?${qs}` : ""}`);
  },
  detail: (id: string) => get<InvoiceDetail>(`/invoices/${id}`),
  approve: (id: string, action: "APPROVE" | "REJECT", comment: string) =>
    post<InvoiceApproveResponse>(`/invoices/${id}/approve`, { action, comment }),
};

/** Full invoice upload flow: request presigned URL, then POST file to S3. */
export async function uploadInvoice(file: File): Promise<string> {
  const { documentId, uploadUrl } = await invoicesApi.requestUpload(file.name, file.type);
  await uploadToS3(uploadUrl, file);
  return documentId;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────
export const chatApi = {
  ask: (question: string, sessionId?: string, categoryFilter?: string) =>
    post<ChatResponse>("/chat", { question, sessionId, categoryFilter }),
};

// ─── Documents ──────────────────────────────────────────────────────────────
export const documentsApi = {
  list: (category?: DocumentCategory) =>
    get<PaginatedResponse<DocumentListItem>>(
      `/documents${category ? `?category=${category}` : ""}`,
    ),
  requestUpload: (
    fileName: string,
    contentType: string,
    category: DocumentCategory,
    description?: string,
  ) =>
    post<DocumentUploadResponse>("/documents/upload", {
      fileName,
      contentType,
      category,
      description,
    }),
  sync: () => post<KbSyncResponse>("/documents/sync"),
};

/** Full document upload flow: request presigned URL, then POST file to S3. */
export async function uploadDocument(
  file: File,
  category: DocumentCategory,
  description?: string,
): Promise<string> {
  const { documentId, uploadUrl } = await documentsApi.requestUpload(
    file.name,
    file.type,
    category,
    description,
  );
  await uploadToS3(uploadUrl, file);
  return documentId;
}

// ─── Dashboard ──────────────────────────────────────────────────────────────
export const dashboardApi = {
  stats: () => get<DashboardStats>("/dashboard/stats"),
};

// ─── Admin ────────────────────────────────────────────────────────────────────
export const adminApi = {
  seedData: (dataSet = "default") =>
    post<SeedDataResponse>("/admin/seed-data", { dataSet }),
  uploadPurchaseOrder: (body: {
    poNumber: string;
    vendorName: string;
    totalAmount: number;
    currency?: string;
    department?: string;
  }) => post<PurchaseOrderUploadResponse>("/purchase-orders/upload", body),
  uploadGoodsReceipt: (body: {
    grId: string;
    poNumber: string;
    totalQuantityReceived: number;
    status?: string;
  }) => post<GoodsReceiptUploadResponse>("/goods-receipts/upload", body),
  getSettings: () => get<ApprovalSettings>("/admin/settings"),
  updateSettings: (body: ApprovalSettings) =>
    put<ApprovalSettings>("/admin/settings", body),
};

// ─── Records Assistant (chat) — streaming, citations, session summary ─────────
//
// These helpers back the floating Records Assistant widget. They intentionally
// use the shared `http` axios instance (JWT + error handling) for JSON calls
// and native `fetch` for the SSE stream (axios cannot expose a ReadableStream).
// The backend wraps success payloads as { data: ... }, so we read `.data.data`.

/** A single retrieved-source citation attached to an assistant answer. */
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

/**
 * Non-streaming chat call (kept for backward compatibility / fallback).
 * Prefer `streamChatMessage` for the interactive widget.
 */
export async function sendChatMessage(
  question: string,
  sessionId?: string,
): Promise<ChatResponseData> {
  const body: Record<string, string> = { question };
  if (sessionId) body.sessionId = sessionId;
  const { data } = await http.post("/chat", body);
  return data.data as ChatResponseData;
}

// ─── Chat SSE Streaming ───────────────────────────────────────────────────────
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
 * Attaches the bearer token (when present) so the stream authenticates the same
 * way as the shared `http` client.
 */
export async function* streamChatMessage(
  question: string,
  sessionId?: string,
  categoryFilter?: string,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
  const body: Record<string, string> = { question };
  if (sessionId) body.sessionId = sessionId;
  if (categoryFilter) body.categoryFilter = categoryFilter;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = await getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers,
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

// ─── Chat Session Summary & Resume ────────────────────────────────────────────
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
    await http.post(`/chat/sessions/${sessionId}/summary`);
  } catch {
    // fire-and-forget: a failed summary must never surface to the user
  }
}

// GET /chat/sessions/{id} — full message history for the expander.
export async function getSession(sessionId: string): Promise<ChatSessionDetailData> {
  const { data } = await http.get(`/chat/sessions/${sessionId}`);
  return data.data as ChatSessionDetailData;
}

// GET /chat/sessions — returns most recent session including its stored summary, or null.
export async function getLatestSessionSummary(): Promise<ChatSessionSummaryItem | null> {
  const { data } = await http.get("/chat/sessions", { params: { limit: 1 } });
  const sessions = data.data as ChatSessionSummaryItem[];
  return sessions.length > 0 ? sessions[0] : null;
}
