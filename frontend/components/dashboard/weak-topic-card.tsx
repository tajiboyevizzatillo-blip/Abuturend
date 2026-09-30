"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { PracticePlayer } from "@/components/practice/practice-player";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchWeakSkills, startWeakPractice, topicName } from "@/lib/weak-skills";
import type { WeakSkillsResponse } from "@/lib/weak-skills";
import type { PracticeSession } from "@/lib/sessions";
import { cn } from "@/lib/utils";

/** Radar glyph (local, same style as the other dashboard icons). */
function RadarIcon({ size = 19, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={className}
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <path d="M12 12 19 7" />
    </svg>
  );
}

/**
 * Dashboard card: the single weakest topic with a one-click drill.
 *
 * Fetches only the radar endpoint (one small aggregate query server-side) and
 * stays silent when there is nothing weak yet — a dashboard must not nag.
 */
export function WeakTopicCard() {
  const t = useTranslations("weakSkills");
  const locale = useLocale();
  const [data, setData] = useState<WeakSkillsResponse | null>(null);
  const [drilling, setDrilling] = useState<number[] | null>(null);

  useEffect(() => {
    let ignore = false;
    fetchWeakSkills()
      .then((payload) => {
        if (!ignore) setData(payload);
      })
      .catch(() => {
        /* the card is optional decoration - never block the dashboard */
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (drilling) {
    return (
      <PracticePlayer
        startSession={() =>
          startWeakPractice({ topic_ids: drilling }) as Promise<PracticeSession>
        }
      />
    );
  }

  const weakest = data?.weak_topics?.[0];

  return (
    <Card className="rounded-2xl">
      <CardHeader className="flex flex-row items-center justify-between gap-2 sm:px-6 sm:pt-6">
        <CardTitle className="flex items-center gap-2 text-base">
          <RadarIcon className="text-primary" />
          {t("weakTitle")}
        </CardTitle>
        <Link
          href="/weak-skills"
          className="text-sm font-semibold text-primary hover:underline"
        >
          {t("radarTitle")}
        </Link>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 sm:px-6">
        {!data ? (
          <Skeleton className="h-16 rounded-xl" />
        ) : !weakest ? (
          <p className="py-2 text-sm text-subtle">{t("noWeak")}</p>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{topicName(weakest, locale)}</p>
              <p className="text-xs text-subtle">
                {t("wrongCount", { count: weakest.wrong })}
              </p>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-surface-subtle">
                <div
                  className={cn(
                    "h-full rounded-full",
                    weakest.accuracy < 40
                      ? "bg-danger"
                      : weakest.accuracy < 70
                        ? "bg-warning"
                        : "bg-success"
                  )}
                  style={{ width: `${weakest.accuracy}%` }}
                />
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span
                className={cn(
                  "badge",
                  weakest.accuracy < 40
                    ? "badge-danger"
                    : weakest.accuracy < 70
                      ? "badge-warning"
                      : "badge-success"
                )}
              >
                {weakest.accuracy}%
              </span>
              {data.is_premium && weakest.topic_id ? (
                <Button
                  onClick={() => setDrilling([weakest.topic_id as number])}
                  className="btn-primary btn-sm"
                >
                  {t("practice")}
                </Button>
              ) : (
                <Link href="/weak-skills" className="btn btn-ghost btn-sm">
                  {data.is_premium ? t("practice") : t("lockedCta")}
                </Link>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
