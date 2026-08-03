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
