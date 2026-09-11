/**
 * Authentication service — thin wrapper over AWS Amplify (Cognito).
 *
 * Two modes:
 *  - Configured: when VITE_USER_POOL_ID / VITE_USER_POOL_CLIENT_ID are present,
 *    Amplify is configured and real Cognito sign-in / token retrieval is used.
 *  - Dev fallback: when Cognito is NOT configured (local development), a
 *    lightweight mock session is used so the UI can run against the local
 *    backend, which resolves a default dev user when no token is supplied.
 *
 * The backend accepts the id/access token as a Bearer credential (see
 * app/middleware/auth.py). We attach whatever token is available.
 */

import { logger } from "./logger";
import type { UserRole } from "./types";

export interface AuthUser {
  userId: string;
  email: string;
  roles: UserRole[];
}

const USER_POOL_ID = import.meta.env.VITE_USER_POOL_ID ?? "";
const USER_POOL_CLIENT_ID = import.meta.env.VITE_USER_POOL_CLIENT_ID ?? "";
const AWS_REGION = import.meta.env.VITE_AWS_REGION ?? "us-east-1";

/** True when a real Cognito pool is configured (not a placeholder). */
export const isCognitoConfigured = (): boolean => {
  const placeholder = (v: string) =>
    !v || v.includes("XXXX") || v.toUpperCase() === "PLACEHOLDER";
  return !placeholder(USER_POOL_ID) && !placeholder(USER_POOL_CLIENT_ID);
};

// ─── Dev fallback session ─────────────────────────────────────────────────────

const DEV_SESSION_KEY = "intelliprocess.devSession";

/**
 * Dev users selectable on the local login screen. These mirror the roles the
 * backend understands; the backend's dev mode grants ADMIN when no token is
 * present, but the frontend still tracks the selected role for UI gating.
 */
export const DEV_USERS: Record<string, AuthUser> = {
  admin: { userId: "dev-admin", email: "admin@localhost", roles: ["ADMIN"] },
  manager: {
    userId: "dev-manager",
    email: "manager@localhost",
    roles: ["FINANCE_MANAGER"],
  },
  clerk: { userId: "dev-clerk", email: "clerk@localhost", roles: ["AP_CLERK"] },
  staff: { userId: "dev-staff", email: "staff@localhost", roles: ["STAFF"] },
};

// ─── Amplify (lazy) ───────────────────────────────────────────────────────────

let amplifyConfigured = false;

async function ensureAmplify(): Promise<void> {
  if (amplifyConfigured || !isCognitoConfigured()) return;
  const { Amplify } = await import("aws-amplify");
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: USER_POOL_ID,
        userPoolClientId: USER_POOL_CLIENT_ID,
      },
    },
  });
  amplifyConfigured = true;
  logger.info("auth", `Amplify configured for pool ${USER_POOL_ID} (${AWS_REGION})`);
}

function mapGroupsToRoles(groups: unknown): UserRole[] {
  const valid: UserRole[] = ["ADMIN", "FINANCE_MANAGER", "AP_CLERK", "STAFF"];
  const list = Array.isArray(groups)
    ? groups
    : typeof groups === "string"
      ? groups.split(",")
      : [];
  const roles = list
    .map((g) => String(g).trim())
    .filter((g): g is UserRole => (valid as string[]).includes(g));
  return roles.length ? roles : ["STAFF"];
}

// ─── Public API ───────────────────────────────────────────────────────────────

/** Sign in with username/password (Cognito) or select a dev role (fallback). */
export async function signIn(username: string, password: string): Promise<AuthUser> {
  if (!isCognitoConfigured()) {
    // Dev fallback: `username` selects one of DEV_USERS (defaults to admin).
    const key = username.toLowerCase().trim();
    const user = DEV_USERS[key] ?? DEV_USERS.admin;
    sessionStorage.setItem(DEV_SESSION_KEY, JSON.stringify(user));
    logger.info("auth", `Dev sign-in as ${user.email} (${user.roles.join(",")})`);
    return user;
  }

  await ensureAmplify();
  const { signIn: amplifySignIn } = await import("aws-amplify/auth");
  const result = await amplifySignIn({ username, password });
  if (!result.isSignedIn) {
    throw new Error("Additional sign-in steps are required. Please contact your administrator.");
  }
  const user = await getCurrentUser();
  if (!user) throw new Error("Sign-in succeeded but no user session was found.");
  return user;
}

/** Return the current authenticated user, or null if not signed in. */
export async function getCurrentUser(): Promise<AuthUser | null> {
  if (!isCognitoConfigured()) {
    const raw = sessionStorage.getItem(DEV_SESSION_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  }

  try {
    await ensureAmplify();
    const { fetchAuthSession } = await import("aws-amplify/auth");
    const session = await fetchAuthSession();
    const payload = session.tokens?.idToken?.payload;
    if (!payload) return null;
    return {
      userId: String(payload.sub ?? ""),
      email: String(payload.email ?? payload["cognito:username"] ?? ""),
      roles: mapGroupsToRoles(payload["cognito:groups"]),
    };
  } catch (err) {
    logger.debug("auth", "No active session", err);
    return null;
  }
}

/** Return the bearer token to attach to API requests, or null in dev fallback. */
export async function getToken(): Promise<string | null> {
  if (!isCognitoConfigured()) return null; // Local backend uses its dev user.

  try {
    await ensureAmplify();
    const { fetchAuthSession } = await import("aws-amplify/auth");
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() ?? null;
  } catch (err) {
    logger.warn("auth", "Failed to fetch auth token", err);
    return null;
  }
}

/** Sign out and clear any local session. */
export async function signOut(): Promise<void> {
  if (!isCognitoConfigured()) {
    sessionStorage.removeItem(DEV_SESSION_KEY);
    return;
  }
  await ensureAmplify();
  const { signOut: amplifySignOut } = await import("aws-amplify/auth");
  await amplifySignOut();
}
