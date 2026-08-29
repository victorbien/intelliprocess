/**
 * Login page - Cognito authentication form.
 *
 * Dev mode: sign in locally by entering an email and choosing a role. No
 * Cognito call is made; the identity is stored via AuthContext. When Cognito
 * is provisioned, replace handleSubmit with a real sign-in call.
 */

import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth, type UserRole } from "../context/AuthContext";

const ROLES: { value: UserRole; label: string }[] = [
  { value: "ADMIN", label: "Admin" },
  { value: "FINANCE_MANAGER", label: "Finance Manager" },
  { value: "AP_CLERK", label: "AP Clerk" },
  { value: "STAFF", label: "Staff" },
];

interface LocationState {
  from?: { pathname: string };
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("dev@localhost");
  const [role, setRole] = useState<UserRole>("ADMIN");
  const [error, setError] = useState<string | null>(null);

  const redirectTo =
    (location.state as LocationState | null)?.from?.pathname ?? "/invoices";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) {
      setError("Please enter an email.");
      return;
    }
    login(trimmed, role);
    navigate(redirectTo, { replace: true });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mb-2 text-3xl font-bold tracking-tight text-blue-700">
            ⚡ IntelliProcess AI
          </div>
          <p className="text-sm text-gray-500">Sign in to continue</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm"
        >
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="mb-4 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-800 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />

          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="role">
            Role
          </label>
          <select
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="mb-5 w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-800 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>

          {error && (
            <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 border border-red-200">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="w-full rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-medium text-white shadow transition hover:bg-blue-800 active:scale-[0.99]"
          >
            Sign in
          </button>

          <p className="mt-4 text-center text-[11px] text-gray-400">
            Local development sign-in. Cognito is not yet configured.
          </p>
        </form>
      </div>
    </div>
  );
}
