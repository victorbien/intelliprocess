/**
 * Authentication context — holds the current user, exposes sign-in/out, and
 * provides role-check helpers used for route/nav gating (AC-1.2.x).
 */

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as auth from "@/services/auth";
import type { AuthUser } from "@/services/auth";
import { logger } from "@/services/logger";
import type { UserRole } from "@/services/types";

export interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  cognitoConfigured: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** True if the user holds any of the given roles. */
  hasRole: (...roles: UserRole[]) => boolean;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore any existing session on mount.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const current = await auth.getCurrentUser();
        if (active) setUser(current);
      } catch (err) {
        logger.warn("auth", "Failed to restore session", err);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const signedIn = await auth.signIn(username, password);
    setUser(signedIn);
  }, []);

  const signOut = useCallback(async () => {
    await auth.signOut();
    setUser(null);
  }, []);

  const hasRole = useCallback(
    (...roles: UserRole[]) => !!user && roles.some((r) => user.roles.includes(r)),
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAuthenticated: !!user,
      cognitoConfigured: auth.isCognitoConfigured(),
      signIn,
      signOut,
      hasRole,
    }),
    [user, loading, signIn, signOut, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
