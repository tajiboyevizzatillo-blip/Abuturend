"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { PracticePlayer } from "@/components/practice/practice-player";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RadarChart, accuracyTone } from "@/components/weak-skills/radar-chart";
import { ApiError } from "@/lib/api";
import { startWeakPractice } from "@/lib/weak-skills";
import type { PracticeSession } from "@/lib/sessions";
import {
  fetchWeakSkillSubject,
  fetchWeakSkills,
  subjectName,
  topicName,
  type WeakSkillSubjectResponse,
  type WeakSkillsResponse,
  type WeakTopic,
} from "@/lib/weak-skills";
import { cn } from "@/lib/utils";

function shortLabel(name: string, max = 14): string {
  return name.length > max ? `${name.slice(0, max - 1)}вЂ¦` : name;
}

export default function WeakSkillsPage() {
  const t = useTranslations("weakSkills");
  const locale = useLocale();

  const [data, setData] = useState<WeakSkillsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<WeakSkillSubjectResponse | null>(null);
  const [practice, setPractice] = useState<{ topicIds: number[] } | null>(null);
  const [practiceError, setPracticeError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    fetchWeakSkills()
      .then((res) => {
        if (ignore) return;
        setData(res);
        if (res.subjects.length) setSelected(res.subjects[0].subject_id);
      })
      .catch((e: unknown) => {
        if (ignore) return;
        setError(e instanceof ApiError ? String(e.detail ?? e.message) : t("loadError"));
      });
    return () => {
      ignore = true;
    };
  }, [t]);

  // Subject drill-down: loaded lazily so the first paint only needs the radar.
  // The "loading" flag is derived from the selection, not set in the effect
  // (setting state synchronously inside an effect triggers a cascading render).
  const [detailError, setDetailError] = useState<boolean>(false);
  useEffect(() => {
    if (selected === null) return;
    let ignore = false;
    fetchWeakSkillSubject(selected)
      .then((res) => {
        if (ignore) return;
        setDetail(res);
        setDetailError(false);
      })
      .catch(() => {
        if (!ignore) setDetailError(true);
      });
    return () => {
      ignore = true;
    };
  }, [selected]);

  // Loading while the visible detail belongs to another subject than the selected one.
  const detailLoading = selected !== null && detail?.subject.subject_id !== selected && !detailError;
  const selectSubject = (id: number) => {
    // Reset the stale detail so the previous subject's rows are never shown
    // under the newly selected header.
    setDetail(null);
    setSelected(id);
  };

  // Clicking "Mashq qilish" only *arms* the session request: the player owns
  // session creation (and its own 402/daily-limit handling), so opening the
  // player must not create a session twice.
  const armPractice = useCallback((topicIds: number[]) => {
    setPracticeError(null);
    if (!topicIds.length) {
      setPracticeError(t("practiceError"));
      return;
    }
    setPractice({ topicIds });
  }, [t]);

  // The player renders its own ProtectedShell, so the two views never nest.
  if (practice) {
    return (
      <PracticePlayer
        startSession={() =>
          startWeakPractice({ topic_ids: practice.topicIds }) as Promise<PracticeSession>
        }
      />
    );
  }

  if (error) {
    return (
      <ProtectedShell>
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
          <Alert variant="danger">{error}</Alert>
        </div>
      </ProtectedShell>
    );
  }

  if (!data) {
    return (
      <ProtectedShell>
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-72 rounded-2xl" />
          <Skeleton className="h-24 rounded-2xl" />
        </div>
      </ProtectedShell>
    );
  }

  if (!data.has_data) {
    return (
      <ProtectedShell>
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center gap-5 px-4 py-16 text-center sm:px-6">
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft text-3xl">
            рџЋЇ
          </span>
          <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
          <p className="max-w-md text-sm text-subtle">{t("empty")}</p>
          <Link href="/mock-exams" className="btn btn-primary">
            {t("emptyCta")}
          </Link>
        </div>
      </ProtectedShell>
    );
  }

  const labels = data.subjects.map((s) =>
    shortLabel(subjectName(s, locale), 12)
  );
  const isPremium = data.is_premium;
  const hidden = data.hidden_weak_topics;

  return (
    <ProtectedShell>
      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-subtle">{t("subtitle")}</p>
        </div>

        {/* Radar: one axis per subject, value = accuracy %. */}
        <Card className="rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between gap-2 sm:px-6 sm:pt-6">
            <CardTitle className="text-base">{t("radarTitle")}</CardTitle>
            <Badge variant="neutral">
              {t("rules", { min: data.min_answers, threshold: data.threshold })}
            </Badge>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 sm:px-6">
            <RadarChart subjects={data.subjects} labels={labels} />
            {/* Numbers repeat the chart: colour is never the only signal. */}
            <ul className="flex flex-col gap-2">
              {data.subjects.map((subject) => {
                const tone = accuracyTone(subject.accuracy);
                return (
                  <li key={subject.subject_id}>
                    <button
                      type="button"
                      onClick={() => selectSubject(subject.subject_id)}
                      className={cn(
                        "flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition-colors",
                        selected === subject.subject_id
                          ? "border-primary bg-primary-soft"
                          : "border-border hover:bg-surface-subtle"
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate text-sm font-semibold">
                        {subjectName(subject, locale)}
                        {!subject.enough_data && (
                          <span className="ml-2 text-xs font-normal text-subtle">
                            {t("notEnough")}
                          </span>
                        )}
                      </span>
                      <span className="flex shrink-0 items-center gap-2">
                        <span className="tabular-nums text-sm font-bold">
                          {subject.accuracy}%
                        </span>
                        <span className={cn("badge", tone.badge)}>
                          {t("answered", { count: subject.answered })}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        {/* Topics of the selected subject. */}
        <Card className="rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between gap-2 sm:px-6 sm:pt-6">
            <CardTitle className="text-base">
              {detail ? subjectName(detail.subject, locale) : t("topicsTitle")}
            </CardTitle>
            {detail && detail.history?.length ? (
              <span className="text-xs text-subtle">{t("historyNote")}</span>
            ) : null}
          </CardHeader>
          <CardContent className="flex flex-col gap-4 sm:px-6">
            {detailLoading ? (
              <Skeleton className="h-40 rounded-2xl" />
            ) : !detail?.topics.length ? (
              <p className="py-6 text-center text-sm text-subtle">{t("noTopics")}</p>
            ) : (
              detail.topics.map((topic) => (
                <TopicRow
                  key={topic.topic_id ?? "other"}
                  topic={topic}
                  locale={locale}
                  canPractice={isPremium}
                  onPractice={() => topic.topic_id && armPractice([topic.topic_id])}
                />
              ))
            )}
          </CardContent>
        </Card>

        {/* Weakest topics across all subjects. */}
        <Card className="rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between gap-2 sm:px-6 sm:pt-6">
            <CardTitle className="text-base">{t("weakTitle")}</CardTitle>
            {isPremium && data.weak_topics.length > 0 ? (
              <Button
                onClick={() =>
                  armPractice(
                    data.weak_topics
                      .map((topic) => topic.topic_id)
                      .filter((id): id is number => typeof id === "number")
                  )
                }
                className="btn-primary btn-sm"
              >
                {t("practiceAll")}
              </Button>
            ) : null}
          </CardHeader>
          <CardContent className="flex flex-col gap-4 sm:px-6">
            {data.weak_topics.length === 0 ? (
              <p className="py-6 text-center text-sm text-subtle">{t("noWeak")}</p>
            ) : (
              <>
                <ul className="flex flex-col gap-3">
                  {data.weak_topics.map((topic) => (
                    <li
                      key={topic.topic_id ?? "other"}
                      className="flex flex-wrap items-center justify-between gap-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">
                          {topicName(topic, locale)}
                        </p>
                        <p className="text-xs text-subtle">
                          {t("wrongCount", { count: topic.wrong })}
                        </p>
                        <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-surface-subtle">
                          <div
                            className={cn("h-full rounded-full", accuracyTone(topic.accuracy).bar)}
                            style={{ width: `${topic.accuracy}%` }}
                          />
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span
                          className={cn(
                            "badge",
                            accuracyTone(topic.accuracy).badge
                          )}
                        >
                          {topic.accuracy}%
                        </span>
                        <Button
                          onClick={() =>
                            topic.topic_id && armPractice([topic.topic_id])
                          }
                          disabled={!isPremium}
                          className={cn("btn-sm", isPremium ? "btn-primary" : "btn-ghost")}
                        >
                          {t("practice")}
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>

                {/* PRO paywall for the locked part. */}
                {hidden > 0 ? (
                  <div className="flex flex-col items-start gap-3 rounded-xl border border-primary/25 bg-primary-soft p-4">
                    <p className="text-sm font-semibold">
                      {t("lockedTitle", { count: hidden })}
                    </p>
                    <p className="text-xs text-muted">{t("lockedHint")}</p>
                    <Link href="/premium" className="btn btn-primary btn-sm">
                      {t("lockedCta")}
                    </Link>
                  </div>
                ) : null}
              </>
            )}
            {practiceError ? <Alert variant="danger">{practiceError}</Alert> : null}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center gap-3">
          <Link href="/mistakes" className="btn btn-ghost">
            {t("toMistakes")}
          </Link>
          <Link href="/onboarding" className="btn btn-ghost">
            {t("toPlan")}
          </Link>
        </div>
      </div>
    </ProtectedShell>
  );
}

function TopicRow({
  topic,
  locale,
  canPractice,
  onPractice,
}: {
  topic: WeakTopic;
  locale: string;
  canPractice: boolean;
  onPractice: () => void;
}) {
  const t = useTranslations("weakSkills");
  const tone = accuracyTone(topic.accuracy);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">
          {topicName(topic, locale)}
          {topic.is_other ? (
            <span className="ml-2 text-xs font-normal text-subtle">{t("other")}</span>
          ) : null}
        </p>
        {!topic.enough_data ? (
          <p className="text-xs text-subtle">
            {t("notEnoughAnswers", { count: topic.answered })}
          </p>
        ) : (
          <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-surface-subtle">
            <div
              className={cn("h-full rounded-full", tone.bar)}
              style={{ width: `${topic.accuracy}%` }}
            />
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="tabular-nums text-sm font-bold">{topic.accuracy}%</span>
        <span className={cn("badge", tone.badge)}>
          {t("wrongShort", { count: topic.wrong })}
        </span>
        {topic.is_weak && canPractice && topic.topic_id ? (
          <Button onClick={onPractice} className="btn-primary btn-sm">
            {t("practice")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
