"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { CurrentUser, fetchUser } from "@/lib/api";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setUser: (user: CurrentUser | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

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
];

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  return PUBLIC_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  // True only once /auth/me/ gave a definitive answer (user or 401/403).
  // A network hiccup must not be mistaken for "logged out".
  const [authChecked, setAuthChecked] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  const refresh = async () => {
    try {
      const u = await fetchUser();
      setUser(u);
      setAuthChecked(true);
    } catch {
      // Transient failure: keep whatever user we already know.
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
        setAuthChecked(true);
      })
      .catch(() => {
        // Transient failure: keep whatever user we already know.
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (loading || !authChecked || user || isPublicPath(pathname)) return;
    router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, authChecked, user, pathname, router]);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, setUser }}>
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