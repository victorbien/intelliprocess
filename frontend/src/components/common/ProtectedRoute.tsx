/**
 * Route guard (AC-1.1.x, AC-1.2.x).
 *
 * - Unauthenticated users are redirected to /login.
 * - When `roles` is provided, users lacking those roles are shown a 403 notice
 *   rather than the protected content.
 */

import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "@/context/useAuth";
import type { UserRole } from "@/services/types";
import Spinner from "./Spinner";

interface ProtectedRouteProps {
  children: ReactNode;
  roles?: UserRole[];
}

export default function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { isAuthenticated, loading, hasRole } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner label="Checking your session" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (roles && roles.length > 0 && !hasRole(...roles)) {
    return (
      <div className="mx-auto mt-16 max-w-md rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
        <h2 className="text-lg font-semibold text-amber-800">Access restricted</h2>
        <p className="mt-2 text-sm text-amber-700">
          You do not have permission to view this page. If you believe this is a
          mistake, contact your administrator.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
