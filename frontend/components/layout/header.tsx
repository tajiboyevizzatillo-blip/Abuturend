"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "./locale-switcher";
import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";
import { MobileNav } from "./mobile-nav";

export function Header() {
  const t = useTranslations("nav");

  return (
    <header className="sticky top-3 z-40 px-4 sm:px-6">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 rounded-full border border-border bg-surface/85 px-4 shadow-raised backdrop-blur-md sm:px-5 dark:bg-surface/80">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-navy text-primary-foreground shadow-raised">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
              <path d="M6 12v5c3 3 9 3 12 0v-5" />
            </svg>
          </span>
          <span className="text-lg font-extrabold tracking-tight">
            Abiturend
          </span>
        </Link>

        <nav className="hidden items-center gap-6 text-sm font-medium text-muted md:flex">
          <Link href="/subjects" className="transition-colors hover:text-foreground">
            {t("subjects")}
          </Link>
          <Link href="/mock-exams" className="transition-colors hover:text-foreground">
            {t("mockExams")}
          </Link>
          <Link href="/mistakes" className="transition-colors hover:text-foreground">
            {t("mistakes")}
          </Link>
          <Link href="/weak-skills" className="transition-colors hover:text-foreground">
            {t("weakSkills")}
          </Link>
          <Link href="/leaderboard" className="transition-colors hover:text-foreground">
            {t("leaderboard")}
          </Link>
          <Link href="/universities" className="transition-colors hover:text-foreground">
            {t("universities")}
          </Link>
          <Link
            href="/premium"
            className="transition-colors hover:text-foreground"
          >
            {t("premium")}
          </Link>
          <Link
            href="/achievements"
            className="transition-colors hover:text-foreground"
          >
            {t("achievements")}
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          <MobileNav />
          <LocaleSwitcher className="hidden sm:block" />
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}