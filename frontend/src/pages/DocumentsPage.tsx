import { useEffect, useRef, useState } from "react";
import {
  listDocuments,
  requestDocumentUploadUrl,
  type DocumentListItem,
} from "../services/api";

const CATEGORIES = ["policies", "contracts", "finance", "procurement", "general"];
const ALLOWED_TYPES: Record<string, string> = {
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".txt": "text/plain",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [category, setCategory] = useState("policies");
  const [description, setDescription] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    setLoading(true);
    listDocuments()
      .then((r) => setDocs(r.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    const contentType = ALLOWED_TYPES[ext];
    if (!contentType) {
      setUploadMsg("❌ Use PDF, DOCX, or TXT.");
      return;
    }

    setUploading(true);
    setUploadMsg("");
    try {
      const result = await requestDocumentUploadUrl(
        file.name, contentType, category, description || undefined
      );
      setUploadMsg(`✅ Upload URL obtained (id: ${result.documentId}). `
        + `In production the file would go to S3, then require a KB sync.`);
      load();
    } catch (err: any) {
      setUploadMsg(`❌ ${err?.response?.data?.error ?? err?.message ?? "Upload failed."}`);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
      setDescription("");
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Organizational Documents</h1>

      {/* Upload card */}
      <div className="bg-white border rounded-lg p-5 shadow-sm">
        <h2 className="text-base font-semibold text-gray-700 mb-3">Upload Document (Admin)</h2>
        <form onSubmit={handleUpload} className="flex flex-col gap-3">
          <div className="flex items-center gap-3 flex-wrap">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="text-sm border rounded px-2 py-1.5 text-gray-700"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
              ))}
            </select>
            <input
              type="text"
              placeholder="Description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              className="text-sm border rounded px-2 py-1.5 text-gray-700 flex-1 min-w-0"
            />
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.txt"
              className="text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-green-50 file:text-green-700 hover:file:bg-green-100"
            />
            <button
              type="submit"
              disabled={uploading}
              className="px-4 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
            >
              {uploading ? "Uploading…" : "Upload"}
            </button>
            <button
              type="button"
              onClick={load}
              className="px-3 py-1.5 bg-gray-100 text-gray-600 text-sm rounded hover:bg-gray-200"
            >
              Refresh
            </button>
          </div>
        </form>
        {uploadMsg && <p className="mt-2 text-sm text-gray-700 break-all">{uploadMsg}</p>}
      </div>

      {/* Documents table */}
      {loading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : docs.length === 0 ? (
        <p className="text-gray-500 text-sm">No documents uploaded yet.</p>
      ) : (
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                {["File Name","Category","Uploaded","KB Status","Description"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {docs.map((doc) => (
                <tr key={doc.documentId} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800 max-w-xs truncate">{doc.fileName}</td>
                  <td className="px-4 py-3">
                    <span className="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded font-medium">
                      {doc.category}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(doc.uploadedAt).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      doc.kbSyncStatus === "SYNCED"
                        ? "bg-green-100 text-green-700"
                        : "bg-yellow-100 text-yellow-700"
                    }`}>
                      {doc.kbSyncStatus ?? "PENDING"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs truncate max-w-xs">
                    {doc.description ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
