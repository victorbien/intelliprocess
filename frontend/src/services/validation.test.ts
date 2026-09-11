import { describe, it, expect } from "vitest";

import {
  MAX_FILE_SIZE_BYTES,
  validateInvoiceFile,
  validateRecordFile,
} from "./validation";

function makeFile(name: string, type: string, size: number): File {
  const file = new File(["x"], name, { type });
  // File size is read-only; redefine for the test.
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("validateInvoiceFile", () => {
  it("accepts a valid PDF", () => {
    const result = validateInvoiceFile(makeFile("invoice.pdf", "application/pdf", 1000));
    expect(result.valid).toBe(true);
  });

  it("accepts PNG and JPEG", () => {
    expect(validateInvoiceFile(makeFile("scan.png", "image/png", 1000)).valid).toBe(true);
    expect(validateInvoiceFile(makeFile("scan.jpeg", "image/jpeg", 1000)).valid).toBe(true);
  });

  it("rejects an unsupported extension", () => {
    const result = validateInvoiceFile(makeFile("notes.txt", "text/plain", 1000));
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/unsupported/i);
  });

  it("rejects a file over the 10MB limit", () => {
    const result = validateInvoiceFile(
      makeFile("big.pdf", "application/pdf", MAX_FILE_SIZE_BYTES + 1),
    );
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/10 ?MB/i);
  });

  it("rejects an empty file", () => {
    expect(validateInvoiceFile(makeFile("empty.pdf", "application/pdf", 0)).valid).toBe(false);
  });

  it("rejects when no file is provided", () => {
    expect(validateInvoiceFile(null).valid).toBe(false);
  });
});

describe("validateRecordFile", () => {
  it("accepts PDF, DOCX, and TXT", () => {
    expect(validateRecordFile(makeFile("policy.pdf", "application/pdf", 500)).valid).toBe(true);
    expect(
      validateRecordFile(
        makeFile(
          "policy.docx",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          500,
        ),
      ).valid,
    ).toBe(true);
    expect(validateRecordFile(makeFile("policy.txt", "text/plain", 500)).valid).toBe(true);
  });

  it("rejects an image", () => {
    expect(validateRecordFile(makeFile("scan.png", "image/png", 500)).valid).toBe(false);
  });
});
