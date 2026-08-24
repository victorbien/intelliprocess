/**
 * Admin document upload for the Knowledge Base (AC-2.2.x).
 *
 * Validates the file (PDF/DOCX/TXT, 10 MB), collects a category + optional
 * description, then requests a presigned URL and uploads to S3.
 */

import { useRef, useState } from "react";

import { uploadDocument } from "@/services/api";
import { ApiError, type DocumentCategory } from "@/services/types";
import { validateRecordFile } from "@/services/validation";
import { logger } from "@/services/logger";

const CATEGORIES: DocumentCategory[] = [
  "policies",
  "contracts",
  "finance",
  "procurement",
  "general",
];

interface DocumentUploadProps {
  onUploaded?: () => void;
}

export default function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<DocumentCategory>("policies");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  const submit = async () => {
    const result = validateRecordFile(file);
    if (!result.valid) {
      setMessage({ tone: "err", text: result.error ?? "Invalid file." });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await uploadDocument(file as File, category, description.trim() || undefined);
      logger.info("admin", "Document uploaded");
      setMessage({ tone: "ok", text: "Document uploaded. Trigger a KB sync to make it searchable." });
      setFile(null);
      setDescription("");
      if (inputRef.current) inputRef.current.value = "";
      onUploaded?.();
    } catch (err) {
      const text = err instanceof ApiError ? err.message : "Upload failed.";
      setMessage({ tone: "err", text });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt,application/pdf,text/plain"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-indigo-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-medium text-slate-600">Category</span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as DocumentCategory)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-600">Description (optional)</span>
          <input
            type="text"
            value={description}
            maxLength={500}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
          />
        </label>
      </div>

      {message && (
        <p
          role={message.tone === "err" ? "alert" : "status"}
          className={`text-sm ${message.tone === "err" ? "text-red-700" : "text-green-700"}`}
        >
          {message.text}
        </p>
      )}

      <button
        type="button"
        disabled={busy || !file}
        onClick={() => void submit()}
        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-60"
      >
        {busy ? "Uploading…" : "Upload document"}
      </button>
    </div>
  );
}
