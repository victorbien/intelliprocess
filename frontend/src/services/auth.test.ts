import { describe, it, expect, beforeEach } from "vitest";

import {
  DEV_USERS,
  getCurrentUser,
  getToken,
  isCognitoConfigured,
  signIn,
  signOut,
} from "./auth";

describe("auth service (dev fallback)", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("reports Cognito as not configured in the test environment", () => {
    // No VITE_USER_POOL_ID is set under vitest.
    expect(isCognitoConfigured()).toBe(false);
  });

  it("signs in as the selected dev role and persists the session", async () => {
    const user = await signIn("manager", "");
    expect(user.roles).toContain("FINANCE_MANAGER");

    const restored = await getCurrentUser();
    expect(restored?.email).toBe(DEV_USERS.manager.email);
  });

  it("defaults to admin for an unknown dev role key", async () => {
    const user = await signIn("does-not-exist", "");
    expect(user.roles).toContain("ADMIN");
  });

  it("returns null token in dev fallback (backend uses its dev user)", async () => {
    await signIn("clerk", "");
    expect(await getToken()).toBeNull();
  });

  it("clears the session on sign-out", async () => {
    await signIn("admin", "");
    await signOut();
    expect(await getCurrentUser()).toBeNull();
  });
});
