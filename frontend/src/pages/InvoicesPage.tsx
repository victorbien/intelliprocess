import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  listInvoices,
  requestInvoiceUploadUrl,
  type InvoiceListItem,
} from "../services/api";
import StatusBadge from "../components/common/StatusBadge";

const ALLOWED = ["application/pdf", "image/png", "image/jpeg"];
const MAX_MB = 10;

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    setLoading(true);
    listInvoices()
      .then((res) => setInvoices(res.items))
      .catch(() => setError("Could not load invoices."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    if (!ALLOWED.includes(file.type)) {
      setUploadMsg("❌ Unsupported format. Use PDF, PNG, or JPEG.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setUploadMsg(`❌ File exceeds ${MAX_MB} MB limit.`);
      return;
    }

    setUploading(true);
    setUploadMsg("");
    try {
      const result = await requestInvoiceUploadUrl(file.name, file.type);
      setUploadMsg(`✅ Upload URL obtained (documentId: ${result.documentId}). `
        + `In production the file would now go to S3.`);
      // In real flow: await uploadFileToS3(result.uploadUrl, file);
      load();
    } catch (err: any) {
      const msg = err?.response?.data?.error ?? err?.message ?? "Upload failed.";
      setUploadMsg(`❌ ${msg}`);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Invoices</h1>

      {/* Upload card */}
      <div className="bg-white border rounded-lg p-5 shadow-sm">
        <h2 className="text-base font-semibold text-gray-700 mb-3">Upload Invoice</h2>
        <form onSubmit={handleUpload} className="flex items-center gap-3 flex-wrap">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.png,.jpeg,.jpg"
            className="text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          <button
            type="submit"
            disabled={uploading}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
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
        </form>
        {uploadMsg && (
          <p className="mt-2 text-sm text-gray-700 break-all">{uploadMsg}</p>
        )}
      </div>

      {/* Invoice table */}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : invoices.length === 0 ? (
        <p className="text-gray-500 text-sm">No invoices yet. Upload one above.</p>
      ) : (
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                {["File Name", "Status", "Vendor", "Amount", "Uploaded", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {invoices.map((inv) => (
                <tr key={inv.documentId} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800 max-w-xs truncate">
                    {inv.fileName}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-600">{inv.vendorName ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {inv.totalAmount != null ? `$${inv.totalAmount.toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(inv.uploadedAt).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/invoices/${inv.documentId}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      View →
                    </Link>
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
