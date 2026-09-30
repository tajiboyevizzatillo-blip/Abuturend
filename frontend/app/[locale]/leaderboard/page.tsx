"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/leaderboard";
import { cn } from "@/lib/utils";

const MEDAL: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };

export default function LeaderboardPage() {
  const t = useTranslations("leaderboard");
  const common = useTranslations("common");
  const [entries, setEntries] = useState<LeaderboardEntry[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let ignore = false;
    fetchLeaderboard(50)
      .then((data) => {
        if (!ignore) setEntries(data);
      })
      .catch(() => {
        if (!ignore) setError(true);
      });
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-subtle">{t("subtitle")}</p>
      </div>

      {error ? <Alert variant="danger">{common("error")}</Alert> : null}

      {!entries && !error ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20 rounded-2xl" />
          ))}
        </div>
      ) : entries && entries.length === 0 ? (
        <div className="card flex flex-col items-center gap-4 p-12 text-center">
          <span className="text-5xl">🏆</span>
          <p className="text-lg font-semibold">{t("empty")}</p>
          <p className="max-w-md text-sm text-subtle">{t("emptyHint")}</p>
          <Link href="/register" className="btn btn-primary">
            {t("join")}
          </Link>
        </div>
      ) : entries ? (
        <div className="flex flex-col gap-3">
          {entries.map((e) => (
            <div
              key={e.rank}
              className={cn(
                "card flex items-center gap-4 p-4 sm:p-5",
                e.rank <= 3 && "border-primary/30 bg-primary-soft/40"
              )}
            >
              <span
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-lg font-extrabold"
                aria-label={`${t("rank")} ${e.rank}`}
              >
                {MEDAL[e.rank] ?? (
                  <span className="text-sm font-bold text-muted">{e.rank}</span>
                )}
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <p className="truncate font-semibold">{e.display_name}</p>
                <p className="text-xs text-subtle">
                  {t("sessions")}: {e.finished_sessions}
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <span className="badge badge-success">
                  {t("correct")}: {e.correct_answers}
                </span>
                <span className="text-xs font-semibold text-muted tabular-nums">
                  {t("accuracy")}: {e.accuracy_percent}%
                </span>
              </div>
            </div>
          ))}
          <p className="text-center text-xs text-subtle">{t("updated")}</p>
        </div>
      ) : null}
    </div>
  );
}
