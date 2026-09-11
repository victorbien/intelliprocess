/**
 * Invoice upload with drag-and-drop + client-side validation (AC-2.1.x).
 *
 * Flow: validate file -> request presigned URL -> POST to S3. On success the
 * parent is notified so it can refresh the invoice list.
 */

import { useCallback, useRef, useState, type DragEvent } from "react";

import { uploadInvoice } from "@/services/api";
import { ApiError } from "@/services/types";
import { logger } from "@/services/logger";
import { validateInvoiceFile } from "@/services/validation";

type UploadState = "idle" | "validating" | "uploading" | "success" | "error";

interface InvoiceUploadProps {
  onUploaded?: (documentId: string) => void;
}

const ACCEPT = ".pdf,.png,.jpeg,.jpg,application/pdf,image/png,image/jpeg";

export default function InvoiceUpload({ onUploaded }: InvoiceUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setFileName(file.name);
      setState("validating");
      setMessage(null);

      const result = validateInvoiceFile(file);
      if (!result.valid) {
        setState("error");
        setMessage(result.error ?? "Invalid file.");
        return;
      }

      setState("uploading");
      try {
        const documentId = await uploadInvoice(file);
        logger.info("upload", `Invoice uploaded: ${documentId}`);
        setState("success");
        setMessage(`Uploaded "${file.name}". Processing has started.`);
        onUploaded?.(documentId);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Upload failed. Please try again.";
        setState("error");
        setMessage(msg);
      }
    },
    [onUploaded],
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  const busy = state === "validating" || state === "uploading";

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload invoice. Drag and drop a file here or press Enter to browse."
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !busy) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
          dragging
            ? "border-indigo-500 bg-indigo-50"
            : "border-slate-300 bg-white hover:border-indigo-400"
        } ${busy ? "pointer-events-none opacity-70" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
            e.target.value = ""; // allow re-selecting the same file
          }}
        />
        <p className="text-sm font-medium text-slate-700">
          {busy ? "Uploading…" : "Drag & drop an invoice here, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-slate-400">PDF, PNG, or JPEG — up to 10 MB</p>
        {fileName && !busy && (
          <p className="mt-2 text-xs text-slate-500">Selected: {fileName}</p>
        )}
      </div>

      {message && (
        <p
          role={state === "error" ? "alert" : "status"}
          className={`mt-3 rounded-md px-3 py-2 text-sm ${
            state === "error"
              ? "bg-red-50 text-red-700"
              : "bg-green-50 text-green-700"
          }`}
        >
          {message}
        </p>
      )}
    </div>
  );
}
