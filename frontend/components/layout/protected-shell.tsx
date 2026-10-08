"use client";

import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { usePathname } from "@/i18n/navigation";
import {
  isPublicPath,
  useAuth,
} from "@/components/providers/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";

export function ProtectedShell({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();
  const pathname = usePathname();
  // Several pages reuse this shell while remaining reachable when logged out
  // (/subjects, /mock-exams, /premium, /achievements, /universities). Gating on
  // `!user` alone would strand a guest on a permanent skeleton with an empty
  // catalogue, so the public-path exemption AuthProvider applies is applied
  // here too.
  const requiresUser = !isPublicPath(pathname);

  return (
    <>
      <Header />
      <main className="flex flex-1 flex-col">
        {loading ? (
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-8 sm:px-6">
            <Skeleton className="h-8 w-64" />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32" />
              ))}
            </div>
          </div>
        ) : requiresUser && !user ? (
          // On a protected route AuthProvider owns the redirect to /login.
          // Rendering `children` here mounted the whole page and fired its data
          // fetches (401s), flashing private UI and wasting a round of requests.
          <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6">
            <Skeleton className="h-8 w-64" />
          </div>
        ) : (
          <div className="flex flex-1 flex-col">{children}</div>
        )}
      </main>
      <Footer />
    </>
  );
}