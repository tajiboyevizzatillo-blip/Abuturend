"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/leaderboard";
import { Reveal } from "./reveal";

const MEDALS: Record<number, { ring: string; text: string; label: string }> = {
  1: { ring: "from-amber-300 to-yellow-500", text: "text-amber-500", label: "🥇" },
  2: { ring: "from-slate-200 to-slate-400", text: "text-slate-400", label: "🥈" },
  3: { ring: "from-orange-300 to-amber-600", text: "text-amber-600", label: "🥉" },
};

export function Leaderboard() {
  const t = useTranslations("landing");
  const [entries, setEntries] = useState<LeaderboardEntry[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLeaderboard()
      .then((data) => {
        if (!cancelled) setEntries(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        // Degrade to the empty/join state instead of blanking the section.
        if (!cancelled) setEntries([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!entries) {
    return (
      <div className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
        <div className="glass-strong grid gap-4 rounded-[1.75rem] p-8 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-24 w-full" />
          ))}
        </div>
      </div>
    );
  }
  if (entries.length === 0) {
    return (
      <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
        <Reveal>
          <div className="mb-10 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <span className="badge badge-warning mb-4">
                {t("leaderboardTag")}
              </span>
              <h2 className="text-display-sm">{t("leaderboardTitle")}</h2>
              <p className="mt-3 text-lg text-muted">{t("leaderboardSubtitle")}</p>
            </div>
          </div>
        </Reveal>
        <Reveal delay={100}>
          <div className="mesh noise-overlay relative overflow-hidden rounded-[1.75rem] border border-border p-12 text-center sm:p-16">
            <div aria-hidden className="orb orb-blue left-[-4rem] top-[-4rem] h-72 w-72 opacity-70" />
            <div aria-hidden className="orb orb-amber bottom-[-5rem] right-[-3rem] h-72 w-72 opacity-60" />
            <div className="relative z-10 flex flex-col items-center gap-5">
              <span className="text-6xl">🏆</span>
              <h3 className="text-2xl font-bold tracking-tight sm:text-3xl">
                {t("leaderboardEmptyTitle")}
              </h3>
              <p className="max-w-md text-muted">{t("leaderboardEmptyDesc")}</p>
              <Link href="/register" className="btn btn-cta mt-2 px-8 py-3">
                {t("leaderboardJoin")}
                <span aria-hidden>→</span>
              </Link>
            </div>
          </div>
        </Reveal>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
      <Reveal>
        <div className="mb-10 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <span className="badge badge-warning mb-4">
              {t("leaderboardTag")}
            </span>
            <h2 className="text-display-sm">{t("leaderboardTitle")}</h2>
            <p className="mt-3 text-lg text-muted">{t("leaderboardSubtitle")}</p>
          </div>
          <Link href="/register" className="btn btn-secondary btn-sm shrink-0">
            {t("leaderboardJoin")}
            <span aria-hidden>→</span>
          </Link>
        </div>
      </Reveal>

      <Reveal delay={100}>
        <div className="glass-strong overflow-hidden rounded-[1.75rem]">
          {entries.map((e, i) => {
            const medal = MEDALS[e.rank];
            const left =
              i < entries.length - 1 ? "border-b border-border/60" : "";
            return (
              <div
                key={e.rank}
                className={`flex items-center gap-4 px-5 py-4 sm:px-7 ${left} ${e.rank <= 3 ? "bg-primary-soft/40" : ""}`}
              >
                <span className="flex w-10 shrink-0 justify-center text-2xl">
                  {medal?.label ?? (
                    <span className="text-lg font-bold tabular-nums text-muted">
                      {e.rank}
                    </span>
                  )}
                </span>

                <span
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${medal?.ring ?? "from-primary-soft to-primary-muted"} text-lg font-extrabold text-foreground`}
                >
                  {(e.display_name || "?").slice(0, 1).toUpperCase()}
                </span>

                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-foreground">
                    {e.display_name}
                  </p>
                  <p className="text-xs text-muted">
                    {e.finished_sessions} {t("leaderboardSessions")}
                  </p>
                </div>

                <div className="hidden w-44 sm:block">
                  <div className="mb-1 flex justify-between text-xs font-medium text-muted">
                    <span>{t("leaderboardAccuracy")}</span>
                    <span className="tabular-nums text-success">
                      {e.accuracy_percent}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-subtle">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary to-info"
                      style={{ width: `${e.accuracy_percent}%` }}
                    />
                  </div>
                </div>

                <span className="w-24 shrink-0 text-right text-lg font-extrabold tabular-nums tracking-tight">
                  {e.correct_answers}
                  <span className="ml-1 text-xs font-semibold text-muted">
                    {t("leaderboardPoints")}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </Reveal>
    </section>
  );
}