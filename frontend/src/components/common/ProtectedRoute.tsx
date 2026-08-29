/**
 * Route guard - redirects to /login if unauthenticated.
 * Optionally checks required role.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth, type UserRole } from "../../context/AuthContext";

interface ProtectedRouteProps {
  /** When provided, the user must hold one of these roles to view the route. */
  allowedRoles?: UserRole[];
}

export default function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  // Wait for the persisted session to be restored before deciding.
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-gray-400">
        Loading…
      </div>
    );
  }

  if (!isAuthenticated) {
    // Remember where the user was headed so login can send them back.
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    // Authenticated but lacking the required role.
    return <Navigate to="/invoices" replace />;
  }

  return <Outlet />;
}
