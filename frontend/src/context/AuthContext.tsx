/**
 * Authentication context provider.
 *
 * Provides:
 * - user (current user info + role)
 * - isAuthenticated
 * - login / logout actions
 * - loading state
 *
 * Dev mode: authentication is handled locally. The login form lets a developer
 * pick a role and sign in without Cognito; the selected identity is persisted
 * to localStorage so a page refresh keeps the session. The backend already
 * accepts a default dev user when STAGE=dev, so no token is required for API
 * calls in this mode.
 *
 * Production: this is the single integration point for Amazon Cognito. Replace
 * `login` with a Cognito sign-in call and store the returned token, then send
 * it as an Authorization header from the API layer. The rest of the app depends
 * only on the shape exposed here, so swapping the backend does not require UI
 * changes.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type UserRole = "AP_CLERK" | "FINANCE_MANAGER" | "STAFF" | "ADMIN";

export interface AuthUser {
  userId: string;
  email: string;
  role: UserRole;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, role: UserRole) => void;
  logout: () => void;
}

const STORAGE_KEY = "intelliprocess.auth.user";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthUser;
    if (parsed && parsed.userId && parsed.email && parsed.role) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore any persisted session on first mount.
  useEffect(() => {
    setUser(readStoredUser());
    setLoading(false);
  }, []);

  const login = useCallback((email: string, role: UserRole) => {
    const nextUser: AuthUser = {
      // Keep the dev backend's default user id so persisted records line up
      // with what the API attributes to the dev user.
      userId: "dev-user-001",
      email,
      role,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextUser));
    setUser(nextUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      loading,
      login,
      logout,
    }),
    [user, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
