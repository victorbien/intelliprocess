/**
 * Shared TypeScript types mirroring the backend API contracts.
 *
 * Response envelope (docs/09-api-specification.md):
 *   Success: { statusCode, data }
 *   Error:   { statusCode, error: { code, message } }
 */

// ─── Enums ────────────────────────────────────────────────────────────────

export type UserRole = "AP_CLERK" | "FINANCE_MANAGER" | "STAFF" | "ADMIN";

export type InvoiceStatus =
  | "UPLOADED"
  | "PROCESSING"
  | "EXTRACTED"
  | "APPROVED"
  | "ESCALATED"
  | "REJECTED"
  | "ERROR";

export type DocumentCategory =
  | "policies"
  | "contracts"
  | "finance"
  | "procurement"
  | "general";

// ─── Response envelope ──────────────────────────────────────────────────────

export interface ApiSuccess<T> {
  statusCode: number;
  data: T;
}

export interface PaginatedResponse<T> {
  items: T[];
  count: number;
  next_key?: string | null;
}

export interface PresignedPost {
  url: string;
  fields: Record<string, string>;
}

// ─── Invoices ─────────────────────────────────────────────────────────────

export interface InvoiceUploadResponse {
  documentId: string;
  uploadUrl: PresignedPost;
  expiresIn: number;
}

export interface InvoiceListItem {
  documentId: string;
  fileName: string;
  status: InvoiceStatus;
  uploadedAt: string;
  uploadedBy: string;
  vendorName?: string | null;
  totalAmount?: number | null;
}

export interface MatchResult {
  threeWayMatch?: string;
  poMatch?: Record<string, unknown>;
  grMatch?: Record<string, unknown>;
  discrepancies?: string[];
  [key: string]: unknown;
}

export interface ApprovalDecision {
  decision?: string;
  approver?: string;
  approvedAt?: string;
  comment?: string;
  reason?: string;
  escalateTo?: string;
  [key: string]: unknown;
}

export interface InvoiceDetail {
  documentId: string;
  fileName: string;
  status: InvoiceStatus;
  uploadedAt: string;
  updatedAt?: string | null;
  uploadedBy: string;
  documentUrl?: string | null;
  extraction?: Record<string, unknown> | null;
  confidence?: Record<string, number> | null;
  overallConfidence?: number | null;
  matchResult?: MatchResult | null;
  approvalDecision?: ApprovalDecision | null;
  errorDetails?: string | null;
  processingDurationMs?: number | null;
}

export interface InvoiceApproveResponse {
  documentId: string;
  newStatus: InvoiceStatus;
  approver: string;
  approvedAt: string;
}

// ─── Chat ─────────────────────────────────────────────────────────────────

export interface Citation {
  documentName: string;
  documentId: string;
  pageNumber?: number | null;
  relevanceScore: number;
  snippet: string;
  category?: string | null;
}

export type ChatSourceType = "documents" | "structured" | "hybrid";

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  sessionId: string;
  sourceType?: ChatSourceType;
  dataSnapshot?: Record<string, unknown> | null;
  unavailable?: boolean | null;
  responseTimeMs: number;
}

// ─── Documents ──────────────────────────────────────────────────────────────

export interface DocumentUploadResponse {
  documentId: string;
  uploadUrl: PresignedPost;
  expiresIn: number;
  note?: string;
}

export interface DocumentListItem {
  documentId: string;
  fileName: string;
  category: DocumentCategory;
  uploadedAt: string;
  description?: string | null;
  kbSyncStatus?: string | null;
}

// ─── Dashboard ──────────────────────────────────────────────────────────────

export interface RecentActivityItem {
  documentId: string;
  fileName: string;
  action: string;
  timestamp: string;
  actor: string;
}

export interface SupplierBreakdownItem {
  vendorName: string;
  invoiceCount: number;
  totalAmount: number;
}

export interface AmountBucket {
  bucket: string;
  count: number;
}

export interface MatchRateSummary {
  matched: number;
  total: number;
  rate: number;
}

export interface DashboardStats {
  totalInvoices: number;
  statusCounts: Record<string, number>;
  autoApprovalRate: number;
  avgProcessingTimeSec: number;
  recentActivity: RecentActivityItem[];
  supplierBreakdown: SupplierBreakdownItem[];
  amountDistribution: AmountBucket[];
  matchRate?: MatchRateSummary | null;
}

// ─── Admin ────────────────────────────────────────────────────────────────

export interface SeedDataResponse {
  message: string;
  purchaseOrdersCreated: number;
  goodsReceiptsCreated: number;
}

export interface KbSyncResponse {
  message: string;
  syncJobId?: string | null;
}

export interface PurchaseOrderUploadResponse {
  poNumber: string;
  message: string;
}

export interface GoodsReceiptUploadResponse {
  grId: string;
  poNumber: string;
  message: string;
}

// ─── Client-side error ──────────────────────────────────────────────────────

/** Normalized error surfaced to UI components. */
export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status = 0, code = "UNKNOWN") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}
