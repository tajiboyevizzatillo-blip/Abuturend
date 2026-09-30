"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { PracticePlayer } from "@/components/practice/practice-player";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchMistakes,
  MISTAKE_SESSION_LIMIT,
  type MistakeItem,
} from "@/lib/mistakes";
import { cn } from "@/lib/utils";

function localText(item: MistakeItem, locale: string): string {
  if (locale === "ru") return item.text_ru || item.text_uz || "";
  if (locale === "en") return item.text_en || item.text_uz || "";
  return item.text_uz;
}

function localSubject(item: MistakeItem, locale: string): string {
  if (locale === "ru") return item.subject_name_ru || item.subject_name_uz || "";
  if (locale === "en") return item.subject_name_en || item.subject_name_uz || "";
  return item.subject_name_uz || "";
}

export default function MistakesPage() {
  const t = useTranslations("mistakes");
  const locale = useLocale();
  const [items, setItems] = useState<MistakeItem[] | null>(null);
  const [error, setError] = useState(false);
  const [practiceIds, setPracticeIds] = useState<number[] | null>(null);

  useEffect(() => {
    let ignore = false;
    fetchMistakes()
      .then((data) => {
        if (!ignore) setItems(data.items);
      })
      .catch(() => {
        if (!ignore) setError(true);
      });
    return () => {
      ignore = true;
    };
  }, []);

  // The player renders its own ProtectedShell, so the two views never nest.
  if (practiceIds) {
    return <PracticePlayer questionIds={practiceIds} />;
  }

  const active = items?.filter((i) => !i.is_mastered) ?? [];
  const mastered = items?.filter((i) => i.is_mastered) ?? [];
  // The API accepts at most 30 questions per session.
  const drillable = active.slice(0, MISTAKE_SESSION_LIMIT);

  return (
    <ProtectedShell>
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
            <p className="text-sm text-subtle">{t("subtitle")}</p>
          </div>
          {active.length ? (
            <span className="badge badge-danger">{t("count", { count: active.length })}</span>
          ) : null}
        </div>

        {/* Cross-link: the notebook lists questions, the radar groups them by
            topic and accuracy — the two views answer different questions. */}
        <Link href="/weak-skills" className="btn btn-ghost self-start">
          {t("toRadar")}
        </Link>

        {error ? <Alert variant="danger">{t("loadError")}</Alert> : null}

        {!items && !error ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-24 rounded-2xl" />
            <Skeleton className="h-24 rounded-2xl" />
          </div>
        ) : items && active.length === 0 && mastered.length === 0 ? (
          <div className="card flex flex-col items-center gap-4 p-12 text-center">
            <span className="text-5xl">🎉</span>
            <p className="text-lg font-semibold">{t("empty")}</p>
            <p className="max-w-md text-sm text-subtle">{t("emptyHint")}</p>
            <Link href="/mock-exams" className="btn btn-primary">
              {t("goExam")}
            </Link>
          </div>
        ) : items ? (
          <>
            {active.length ? (
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm font-semibold">{t("activeGroup")}</p>
                  <div className="flex items-center gap-3">
                    {active.length > MISTAKE_SESSION_LIMIT ? (
                      <span className="text-xs text-subtle">{t("limitNote")}</span>
                    ) : null}
                    <Button
                      onClick={() => setPracticeIds(drillable.map((i) => i.question_id))}
                      className="btn-primary"
                    >
                      {t("start", { count: drillable.length })}
                    </Button>
                  </div>
                </div>
                <ul className="flex flex-col gap-3">
                  {active.map((item) => (
                    <li key={item.question_id} className="card flex flex-col gap-3 p-5">
                      <p className="font-medium leading-relaxed">
                        {localText(item, locale)}
                      </p>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="badge badge-neutral">
                          {localSubject(item, locale) || t("allSubjects")}
                        </span>
                        <span className="badge badge-danger">
                          {t("wrongCount", { count: item.wrong })}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {mastered.length ? (
              <div className="flex flex-col gap-3">
                <p className="text-sm font-semibold">{t("masteredGroup")}</p>
                <ul className="flex flex-col gap-2">
                  {mastered.map((item) => (
                    <li
                      key={item.question_id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-success/25 bg-success-soft px-4 py-3"
                    >
                      <span className="min-w-0 flex-1 text-sm">
                        {localText(item, locale)}
                      </span>
                      <span
                        className={cn("badge", "badge-success")}
                      >
                        {t("mastered")}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </ProtectedShell>
  );
}
