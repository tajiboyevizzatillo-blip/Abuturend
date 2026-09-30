"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { localizedName } from "@/lib/catalog";
import {
  type OnboardingPlan,
  type PlanDay,
} from "@/lib/onboarding";
import { cn } from "@/lib/utils";

function TickIcon() {
  return (
    <svg
      width={12}
      height={12}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function ProgressBar({ done, total }: { done: number; total: number }) {
  const t = useTranslations("onboarding");
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-subtle">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            pct >= 100 ? "bg-success" : "bg-primary"
          )}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <p className="text-xs text-subtle">
        {t("todayProgress", { done, total })}
      </p>
    </div>
  );
}

/** "Bugungi reja" — today's slice of the 7-day onboarding plan.

Completion is measured from the stats summary the dashboard already loads: the
last entry of ``weekly_activity`` is today, so today's answered count is known
without a second request. An item is ticked once the day's whole question quota
is reached (honest and cheap -- per-item tracking would need its own ledger).
*/
export function TodayPlanCard({
  plan,
  loading,
  error,
  answeredToday,
  onRetry,
}: {
  plan: OnboardingPlan | null;
  loading: boolean;
  error: boolean;
  answeredToday: number;
  onRetry: () => void;
}) {
  const t = useTranslations("dashboard");
  const p = useTranslations("onboarding");
  const locale = useLocale();
  const dateFmt = new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" });

  if (loading) return <Skeleton className="h-48 rounded-2xl" />;

  if (error) {
    return (
      <Alert variant="danger" className="flex items-center justify-between gap-3">
        <span>{p("planLoadError")}</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          {t("retry")}
        </button>
      </Alert>
    );
  }

  const day: PlanDay | null =
    plan && plan.today ? plan.days.find((d) => d.day === plan.today) ?? null : null;

  return (
    <Card className="rounded-2xl">
      <CardHeader className="flex flex-row items-center justify-between gap-2 sm:px-6 sm:pt-6">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-primary">
            <svg
              width={17}
              height={17}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <rect x="3" y="4" width="18" height="18" rx="3" />
              <path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
          </span>
          {p("todayTitle")}
        </CardTitle>
        <Link
          href="/onboarding"
          className="shrink-0 text-sm font-semibold text-primary hover:underline"
        >
          {p("rebuild")}
        </Link>
      </CardHeader>
      <CardContent className="sm:px-6">
        {!plan || !day ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <p className="text-sm text-subtle">{p("noPlan")}</p>
            <Link href="/onboarding" className="btn btn-primary btn-sm">
              {p("createPlan")}
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-subtle">
              <span className="badge badge-neutral">
                {p("dayLabel", { day: day.day })}
              </span>
              <span className="badge badge-primary">
                {p("questionsCount", { count: day.questions })}
              </span>
              <span className="badge badge-info">
                {p("minutesValue", { minutes: day.minutes })}
              </span>
              <span className="ml-auto">{dateFmt.format(new Date(`${day.date}T00:00:00`))}</span>
            </div>
            <ProgressBar done={Math.min(answeredToday, day.questions)} total={day.questions} />
            <ul className="flex flex-col gap-2">
              {day.items.map((item) => {
                // Drill exactly what the plan asks for: topic (when the
                // subject has one) and the item's question count.
                const params = new URLSearchParams();
                if (item.topic) params.set("topic", item.topic.slug);
                params.set("count", String(Math.min(item.questions, 30)));
                const href = item.subject
                  ? `/subjects/${item.subject.slug}/practice?${params.toString()}`
                  : "/subjects";
                const isLast = item === day.items[day.items.length - 1];
                const itemDone =
                  isLast && day.questions > 0 && answeredToday >= day.questions;
                return (
                  <li key={`${item.subject_id}-${item.topic_id ?? "all"}`}>
                    <Link
                      href={href}
                      className={cn(
                        "flex items-center justify-between gap-3 rounded-xl px-4 py-3 transition-colors",
                        itemDone
                          ? "bg-success-soft"
                          : "bg-surface-subtle hover:bg-primary-soft"
                      )}
                    >
                      <span className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium">
                        <span
                          className={cn(
                            "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
                            itemDone
                              ? "border-success bg-success text-white"
                              : "border-dashed border-line"
                          )}
                        >
                          {itemDone ? <TickIcon /> : null}
                        </span>
                        <span className="truncate">
                          {item.subject ? localizedName(item.subject, locale) : p("allSubjects")}
                          {item.topic ? ` · ${localizedName(item.topic, locale)}` : ""}
                        </span>
                      </span>
                      <span className="shrink-0 text-xs font-semibold tabular-nums text-subtle">
                        {p("questionsCount", { count: item.questions })}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
