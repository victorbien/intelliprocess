import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="text-center py-20 space-y-4">
      <h1 className="text-4xl font-bold text-gray-300">404</h1>
      <p className="text-gray-500">Page not found.</p>
      <Link to="/invoices" className="text-blue-600 hover:underline text-sm">
        ← Back to Invoices
      </Link>
    </div>
  );
}
