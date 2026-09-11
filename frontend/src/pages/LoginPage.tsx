/**
 * Login page (AC-1.1.x).
 *
 * In a Cognito-configured environment this collects username + password.
 * In local development (no Cognito), it offers a role picker so reviewers can
 * exercise role-based UI without a real user pool.
 */

import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/context/useAuth";
import { DEV_USERS } from "@/services/auth";
import { logger } from "@/services/logger";

interface LocationState {
  from?: string;
}

export default function LoginPage() {
  const { signIn, isAuthenticated, cognitoConfigured } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState(cognitoConfigured ? "" : "admin");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectTo = (location.state as LocationState | null)?.from ?? "/invoices";

  // Declarative redirect — safe to evaluate during render (no side effect).
  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(username, password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Sign-in failed. Please try again.";
      logger.warn("login", "Sign-in failed", err);
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-lg">
        <h1 className="text-center text-2xl font-bold text-slate-800">IntelliProcess AI</h1>
        <p className="mt-1 text-center text-sm text-slate-500">
          Sign in to continue
        </p>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          {cognitoConfigured ? (
            <>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Email</span>
                <input
                  type="email"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Password</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </label>
            </>
          ) : (
            <label className="block">
              <span className="text-sm font-medium text-slate-700">
                Development role
              </span>
              <select
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {Object.entries(DEV_USERS).map(([key, u]) => (
                  <option key={key} value={key}>
                    {u.roles.join(", ")} — {u.email}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-slate-400">
                Cognito is not configured; using a local development session.
              </span>
            </label>
          )}

          {error && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
