"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { CurrentUser, fetchUser } from "@/lib/api";
import { fetchOnboardingStatus } from "@/lib/onboarding";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setUser: (user: CurrentUser | null) => void;
  /** null = not checked yet, false = nothing to do. */
  needsOnboarding: boolean | null;
  /** Force a fresh status request (after the wizard is finished or rebuilt). */
  recheckOnboarding: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// While the wizard is pending these stay reachable: the wizard page itself, own
// profile (to skip or rebuild the plan) and every public page (marketing,
// catalog, public leaderboard, certificate verification). Everything personal --
// dashboard, subjects practice, mock exams, history, results, achievements,
// mistakes, teacher -- is gated, so the wizard is effectively mandatory without
// making the public catalog unreachable for a brand-new student.
const ONBOARDING_EXEMPT_PATHS = new Set(["/onboarding", "/profile"]);

function isOnboardingExempt(pathname: string): boolean {
  return ONBOARDING_EXEMPT_PATHS.has(pathname) || isPublicPath(pathname);
}

const PUBLIC_PATHS = new Set([
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
]);

// Public marketing/catalog pages must stay reachable while logged out —
// redirecting them to /login made subjects, mock-exams, universities and
// premium look completely broken for guests.
const PUBLIC_PREFIXES = [
  "/subjects",
  "/universities",
  "/mock-exams",
  "/premium",
  "/achievements",
  // Public certificate verification (a verifier only has the printed serial).
  "/verify",
  // Public leaderboard — no personal data, works for guests too.
  "/leaderboard",
];

export function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  return PUBLIC_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  // True when /auth/me/ failed for a reason that says nothing about the session
  // (offline, DNS, 5xx). fetchUser() returns null for a real 401/403 and
  // re-throws otherwise, so this is how a network blip is told apart from being
  // logged out — without it, one second of bad connectivity would bounce the
  // student to the login form and throw away their typing.
  const [authUnavailable, setAuthUnavailable] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  // True while the student still owes us the wizard; null = unknown.
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean | null>(null);
  // Teachers and admins have no DTM study plan, so the wizard never applies.
  const isStudent = user?.role === "student";

  const refresh = async () => {
    try {
      const u = await fetchUser();
      setUser(u);
      setAuthUnavailable(false);
    } catch {
      // Transient failure: keep whatever user we already know.
      setAuthUnavailable(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    fetchUser()
      .then((u) => {
        if (!active) return;
        setUser(u);
        setAuthUnavailable(false);
      })
      .catch(() => {
        if (active) setAuthUnavailable(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Redirect once the check has *completed* and produced a real answer. The
  // original gate required a separate `authChecked` flag, which stayed false
  // whenever /auth/me/ failed for a network reason — leaving a logged-out
  // visitor stuck on a protected page with no user and no way forward. That
  // flag is gone; `authUnavailable` now covers the one case where "no user" is
  // NOT evidence of being logged out, so a transient outage no longer discards
  // a signed-in session.
  useEffect(() => {
    if (loading || user || authUnavailable || isPublicPath(pathname)) return;
    router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, authUnavailable, pathname, router]);

  // Onboarding gate: one status request per session, then the redirect.
  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const loadOnboarding = useCallback(async () => {
    try {
      const status = await fetchOnboardingStatus();
      setNeedsOnboarding(status.needs_onboarding);
    } catch {
      // Never trap the student on an error page because the status call failed.
      setNeedsOnboarding(false);
    } finally {
      setOnboardingChecked(true);
    }
  }, []);

  const checkOnboarding = useCallback(async () => {
    if (!user || !isStudent) return;
    await loadOnboarding();
  }, [user, isStudent, loadOnboarding]);

  useEffect(() => {
    if (!user || !isStudent || onboardingChecked) return;
    let active = true;
    // Mirrors the auth fetch above: the state updates land in the promise
    // callbacks, never synchronously in the effect body.
    fetchOnboardingStatus()
      .then((status) => {
        if (active) setNeedsOnboarding(status.needs_onboarding);
      })
      .catch(() => {
        if (active) setNeedsOnboarding(false);
      })
      .finally(() => {
        if (active) setOnboardingChecked(true);
      });
    return () => {
      active = false;
    };
  }, [user, isStudent, onboardingChecked]);

  useEffect(() => {
    if (!user || !needsOnboarding) return;
    if (isOnboardingExempt(pathname)) return;
    router.replace("/onboarding");
  }, [user, needsOnboarding, pathname, router]);

  const setUserAndCheckOnboarding = useCallback(
    (u: CurrentUser | null) => {
      setUser(u);
      // Fresh login/register: re-evaluate the gate for the new identity.
      setOnboardingChecked(false);
      setNeedsOnboarding(null);
    },
    [setUser]
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        refresh,
        setUser: setUserAndCheckOnboarding,
        needsOnboarding,
        recheckOnboarding: checkOnboarding,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}