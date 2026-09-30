"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { LocaleSwitcher } from "./locale-switcher";
import { ThemeToggle } from "./theme-toggle";
import { useAuth } from "@/components/providers/auth-provider";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

function MenuIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function MobileNav() {
  const t = useTranslations("nav");
  const common = useTranslations("common");
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const id = requestAnimationFrame(() => setOpen(false));
    return () => cancelAnimationFrame(id);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("menu")}
        className="btn btn-ghost btn-sm h-9 w-9 !px-0"
      >
        <MenuIcon />
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label={t("menu")}>
          <div
            className="absolute inset-0 bg-foreground/30 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-0 flex h-full w-80 max-w-[85vw] flex-col border-l border-border bg-surface shadow-popover">
            <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border px-4">
              <span className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-navy text-primary-foreground">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                    <path d="M6 12v5c3 3 9 3 12 0v-5" />
                  </svg>
                </span>
                <span className="font-extrabold tracking-tight">Abiturend</span>
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label={common("cancel")}
                className="btn btn-ghost btn-sm h-9 w-9 !px-0"
              >
                <CloseIcon />
              </button>
            </div>

            <nav className="nice-scroll flex-1 overflow-y-auto px-3 py-4">
              <ul className="flex flex-col gap-1">
                {(
                  [
                    ["/subjects", "subjects"],
                    ["/mock-exams", "mockExams"],
                    ["/mistakes", "mistakes"],
                    ["/weak-skills", "weakSkills"],
                    ["/leaderboard", "leaderboard"],
                    ["/universities", "universities"],
                    ["/premium", "premium"],
                    ["/achievements", "achievements"],
                  ] as const
                ).map(([href, key]) => (
                  <li key={href}>
                    <Link
                      href={href}
                      className={cn(
                        "flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors",
                        pathname.startsWith(href)
                          ? "bg-primary-soft text-primary"
                          : "text-muted hover:bg-surface-subtle hover:text-foreground"
                      )}
                    >
                      {t(key)}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>

            <div className="shrink-0 border-t border-border p-3">
              <AccountSection onNavigate={() => setOpen(false)} />

              <div className="mt-3 flex items-center justify-between gap-3 border-t border-border pt-3">
                <LocaleSwitcher className="flex-1" />
                <ThemeToggle />
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function AccountSection({ onNavigate }: { onNavigate: () => void }) {
  const t = useTranslations("nav");
  const { user, setUser } = useAuth();
  const router = useRouter();

  if (!user) {
    return (
      <div className="flex flex-col gap-2">
        <Link href="/login" className="btn btn-primary" onClick={onNavigate}>
          {t("login")}
        </Link>
        <Link href="/register" className="btn btn-secondary" onClick={onNavigate}>
          {t("register")}
        </Link>
      </div>
    );
  }

  const onLogout = async () => {
    try {
      await api("/auth/logout/", { method: "POST" });
    } finally {
      setUser(null);
      router.replace("/login");
      router.refresh();
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <Link
        href="/profile"
        onClick={onNavigate}
        className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-muted transition-colors hover:bg-surface-subtle hover:text-foreground"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
          {(user.first_name || user.username).charAt(0).toUpperCase()}
        </span>
        <span className="truncate">{user.first_name || user.username}</span>
      </Link>
      <Link
        href="/dashboard"
        onClick={onNavigate}
        className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-muted transition-colors hover:bg-surface-subtle hover:text-foreground"
      >
        {t("dashboard")}
      </Link>
      {user.role === "teacher" || user.role === "admin" || user.is_staff ? (
        <Link
          href="/teacher/questions"
          onClick={onNavigate}
          className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-muted transition-colors hover:bg-surface-subtle hover:text-foreground"
        >
          {t("teacherPanel")}
        </Link>
      ) : null}
      <button
        type="button"
        onClick={onLogout}
        className="mt-1 flex items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-danger transition-colors hover:bg-danger-soft"
      >
        {t("logout")}
      </button>
    </div>
  );
}