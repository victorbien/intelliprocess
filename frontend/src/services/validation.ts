/**
 * Client-side file validation, mirroring backend rules (AC-2.1.x).
 *
 * These checks provide fast feedback before requesting a presigned URL; the
 * backend remains the source of truth and re-validates every upload.
 */

export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

export const INVOICE_CONTENT_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
] as const;

export const RECORD_CONTENT_TYPES = [
  "application/pdf",
  "text/plain",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
] as const;

const INVOICE_EXTENSIONS = [".pdf", ".png", ".jpeg", ".jpg"];
const RECORD_EXTENSIONS = [".pdf", ".docx", ".txt"];

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

function hasExtension(fileName: string, allowed: string[]): boolean {
  const lower = fileName.toLowerCase();
  return allowed.some((ext) => lower.endsWith(ext));
}

function validate(
  file: File | null | undefined,
  allowedTypes: readonly string[],
  allowedExtensions: string[],
  kindLabel: string,
): ValidationResult {
  if (!file) return { valid: false, error: "Please choose a file to upload." };

  if (file.size === 0) return { valid: false, error: "The selected file is empty." };

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, error: "File exceeds the 10 MB limit." };
  }

  // Accept when either the MIME type OR the extension matches, since browsers
  // don't always populate `file.type` (e.g. .txt/.docx can be empty).
  const typeOk = !file.type || allowedTypes.includes(file.type);
  const extOk = hasExtension(file.name, allowedExtensions);
  if (!extOk || (file.type && !typeOk)) {
    return { valid: false, error: `Unsupported file format for ${kindLabel}.` };
  }

  return { valid: true };
}

export function validateInvoiceFile(file: File | null | undefined): ValidationResult {
  return validate(file, INVOICE_CONTENT_TYPES, INVOICE_EXTENSIONS, "invoices (PDF, PNG, JPEG)");
}

export function validateRecordFile(file: File | null | undefined): ValidationResult {
  return validate(file, RECORD_CONTENT_TYPES, RECORD_EXTENSIONS, "records (PDF, DOCX, TXT)");
}
