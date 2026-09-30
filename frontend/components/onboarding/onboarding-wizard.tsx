"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/providers/auth-provider";
import { ApiError, extractFieldError } from "@/lib/api";
import { fetchSubjects, localizedName, type Subject } from "@/lib/catalog";
import {
  fetchDirections,
  localizedDirectionName,
  localizedUniversityName,
  type Direction,
} from "@/lib/universities";
import {
  MAX_DAILY_MINUTES,
  MIN_DAILY_MINUTES,
  fetchOnboardingStatus,
  skipOnboarding,
  submitOnboarding,
  type OnboardingLevel,
  type OnboardingPlan,
  type OnboardingStatus,
} from "@/lib/onboarding";
import { cn } from "@/lib/utils";

const LEVELS: OnboardingLevel[] = ["beginner", "middle", "high"];
const MINUTE_PRESETS = [30, 60, 90, 120, 180];

function Progress({ step }: { step: number }) {
  const t = useTranslations("onboarding");
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn(
              "h-1.5 flex-1 rounded-full transition-colors",
              i <= step ? "bg-primary" : "bg-surface-subtle"
            )}
          />
        ))}
      </div>
      <p className="text-xs font-semibold text-subtle">
        {t("stepOf", { step, total: 3 })}
      </p>
    </div>
  );
}

function DirectionStep({
  directions,
  selected,
  onSelect,
}: {
  directions: Direction[];
  selected: number | null;
  onSelect: (id: number | null) => void;
}) {
  const t = useTranslations("onboarding");
  const locale = useLocale();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return directions;
    return directions.filter((d) => {
      const haystack = [
        d.name_uz,
        d.name_ru,
        d.name_en,
        d.code,
        d.university.name_uz,
        d.university.name_ru,
        d.university.name_en,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [directions, query]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-extrabold tracking-tight">{t("step1Title")}</h2>
        <p className="text-sm text-subtle">{t("step1Hint")}</p>
      </div>
      <input
        className="input"
        type="search"
        value={query}
        placeholder={t("searchPlaceholder")}
        onChange={(e) => setQuery(e.target.value)}
        aria-label={t("searchPlaceholder")}
      />
      <ul className="nice-scroll flex max-h-80 flex-col gap-2 overflow-y-auto">
        <li>
          <button
            type="button"
            onClick={() => onSelect(null)}
            className={cn(
              "w-full rounded-xl border px-4 py-3 text-left text-sm font-semibold transition-colors",
              selected === null
                ? "border-primary bg-primary-soft text-primary"
                : "border-line bg-surface hover:border-primary/40"
            )}
          >
            {t("noDirection")}
          </button>
        </li>
        {filtered.length === 0 ? (
          <li className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-subtle">
            {t("noResults")}
          </li>
        ) : (
          filtered.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                onClick={() => onSelect(d.id)}
                className={cn(
                  "w-full rounded-xl border px-4 py-3 text-left transition-colors",
                  selected === d.id
                    ? "border-primary bg-primary-soft"
                    : "border-line bg-surface hover:border-primary/40"
                )}
              >
                <span className="block text-sm font-semibold">
                  {localizedDirectionName(d, locale)}
                </span>
                <span className="mt-0.5 block text-xs text-subtle">
                  {localizedUniversityName(d.university, locale)}
                  {d.code ? ` · ${d.code}` : ""}
                </span>
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

function SubjectsStep({
  subjects,
  selected,
  onToggle,
  examDate,
  onExamDate,
}: {
  subjects: Subject[];
  selected: number[];
  onToggle: (id: number) => void;
  examDate: string;
  onExamDate: (value: string) => void;
}) {
  const t = useTranslations("onboarding");
  const locale = useLocale();
  const minDate = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const daysLeft = useMemo(() => {
    if (!examDate) return null;
    const target = new Date(`${examDate}T00:00:00`).getTime();
    const now = new Date();
    const todayUtc = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.ceil((target - todayUtc) / 86_400_000);
  }, [examDate]);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-extrabold tracking-tight">{t("step2Title")}</h2>
        <p className="text-sm text-subtle">{t("step2Hint")}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {subjects.map((s) => {
          const active = selected.includes(s.id);
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onToggle(s.id)}
              aria-pressed={active}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-colors",
                active
                  ? "border-primary bg-primary text-white"
                  : "border-line bg-surface hover:border-primary/40"
              )}
            >
              {localizedName(s, locale)}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-subtle">{t("subjectsSelected", { count: selected.length })}</p>
      <div className="flex flex-col gap-1.5">
        <label className="label" htmlFor="exam-date">
          {t("examDateLabel")}
        </label>
        <input
          id="exam-date"
          className="input"
          type="date"
          min={minDate}
          value={examDate}
          onChange={(e) => onExamDate(e.target.value)}
        />
        {daysLeft !== null && daysLeft >= 0 ? (
          <p className="text-xs font-medium text-primary">
            {t("daysLeft", { days: daysLeft })}
          </p>
        ) : (
          <p className="text-xs text-subtle">{t("examDateHint")}</p>
        )}
      </div>
    </div>
  );
}

function EffortStep({
  minutes,
  onMinutes,
  level,
  onLevel,
}: {
  minutes: number;
  onMinutes: (value: number) => void;
  level: OnboardingLevel;
  onLevel: (value: OnboardingLevel) => void;
}) {
  const t = useTranslations("onboarding");
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-extrabold tracking-tight">{t("step3Title")}</h2>
        <p className="text-sm text-subtle">{t("step3Hint")}</p>
      </div>
      <div className="flex flex-col gap-2">
        <span className="label">{t("minutesLabel")}</span>
        <div className="flex flex-wrap gap-2">
          {MINUTE_PRESETS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onMinutes(m)}
              aria-pressed={minutes === m}
              className={cn(
                "rounded-xl border px-4 py-2 text-sm font-semibold transition-colors",
                minutes === m
                  ? "border-primary bg-primary-soft text-primary"
                  : "border-line bg-surface hover:border-primary/40"
              )}
            >
              {t("minutesValue", { minutes: m })}
            </button>
          ))}
        </div>
        <div className="mt-2 flex items-center gap-3">
          <input
            className="input flex-1"
            type="number"
            min={MIN_DAILY_MINUTES}
            max={MAX_DAILY_MINUTES}
            step={5}
            value={minutes}
            onChange={(e) => {
              const value = Number(e.target.value);
              if (Number.isFinite(value)) onMinutes(value);
            }}
            aria-label={t("minutesLabel")}
          />
          <span className="whitespace-nowrap text-sm text-subtle">{t("minutesUnit")}</span>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <span className="label">{t("levelLabel")}</span>
        <div className="flex flex-col gap-2 sm:flex-row">
          {LEVELS.map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => onLevel(l)}
              aria-pressed={level === l}
              className={cn(
                "flex-1 rounded-xl border px-4 py-3 text-left transition-colors",
                level === l
                  ? "border-primary bg-primary-soft"
                  : "border-line bg-surface hover:border-primary/40"
              )}
            >
              <span className="block text-sm font-bold">{t(`levels.${l}`)}</span>
              <span className="mt-0.5 block text-xs text-subtle">
                {t(`levelsHint.${l}`)}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function PlanResult({ plan }: { plan: OnboardingPlan }) {
  const t = useTranslations("onboarding");
  const locale = useLocale();
  const dateFmt = new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" });

  // "Mashqni boshlash" jumps straight into day 1, first block of the plan.
  const firstItem = plan.days[0]?.items[0];
  const firstPracticeHref = firstItem?.subject
    ? `/subjects/${firstItem.subject.slug}/practice?${
        new URLSearchParams({
          ...(firstItem.topic ? { topic: firstItem.topic.slug } : {}),
          count: String(Math.min(firstItem.questions, 30)),
        }).toString()
      }`
    : "/subjects";

  return (
    <div className="page-enter flex flex-col gap-6">
      <div className="bg-navy relative overflow-hidden rounded-3xl p-6 text-white sm:p-8">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-primary/40 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-20 -left-10 h-48 w-48 rounded-full bg-teal/30 blur-3xl"
        />
        <div className="relative flex flex-col gap-3">
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white backdrop-blur-md">
            {t("resultBadge")}
          </span>
          <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
            {plan.profile.direction
              ? localizedDirectionName(
                  {
                    name_uz: plan.profile.direction.name_uz,
                    name_ru: plan.profile.direction.name_ru,
                    name_en: plan.profile.direction.name_en,
                  },
                  locale
                )
              : t("resultTitle")}
          </h2>
          <p className="max-w-2xl text-sm text-slate-200">{t("resultSummary", {
            days: plan.days.length,
            questions: plan.total_questions,
            minutes: plan.profile.daily_minutes,
          })}</p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Badge className="bg-white/15 text-white">
              {t("levelBadge", { level: t(`levels.${plan.profile.level}`) })}
            </Badge>
            {plan.profile.exam_date ? (
              <Badge className="bg-white/15 text-white">
                {t("examBadge", {
                  date: dateFmt.format(new Date(`${plan.profile.exam_date}T00:00:00`)),
                })}
              </Badge>
            ) : null}
            {plan.profile.days_left !== null && plan.profile.days_left >= 0 ? (
              <Badge className="bg-white/15 text-white">
                {t("daysLeft", { days: plan.profile.days_left })}
              </Badge>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-base font-bold">{t("planTitle")}</h3>
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/onboarding" className="btn btn-secondary">
              {t("rebuild")}
            </Link>
            <Link href={firstPracticeHref} className="btn btn-primary">
              {t("startPractice")}
            </Link>
          </div>
        </div>
        {plan.weak_subjects.length ? (
          <Alert variant="info">{t("weakNote", {
            subjects: plan.weak_subjects
              .map((s) => localizedName(s, locale))
              .join(", "),
          })}</Alert>
        ) : null}
        <ul className="flex flex-col gap-3">
          {plan.days.map((day) => (
            <li key={day.day} className="card flex flex-col gap-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-bold">
                  {t("dayLabel", { day: day.day })}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <span className="badge badge-neutral">
                    {dateFmt.format(new Date(`${day.date}T00:00:00`))}
                  </span>
                  <span className="badge badge-primary">
                    {t("questionsCount", { count: day.questions })}
                  </span>
                  <span className="badge badge-info">
                    {t("minutesValue", { minutes: day.minutes })}
                  </span>
                </span>
              </div>
              <ul className="flex flex-col gap-2">
                {day.items.map((item) => (
                  <li
                    key={`${day.day}-${item.subject_id}-${item.topic_id ?? "all"}`}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface-subtle px-3 py-2 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate font-medium">
                      {item.subject ? localizedName(item.subject, locale) : t("allSubjects")}
                      {item.topic ? ` · ${localizedName(item.topic, locale)}` : ""}
                    </span>
                    <span className="shrink-0 text-xs tabular-nums text-subtle">
                      {t("questionsCount", { count: item.questions })}
                    </span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function OnboardingWizard() {
  const t = useTranslations("onboarding");
  const common = useTranslations("common");
  const { user, loading: authLoading, recheckOnboarding } = useAuth();
  const router = useRouter();

  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [directions, setDirections] = useState<Direction[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [plan, setPlan] = useState<OnboardingPlan | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const [step, setStep] = useState(1);
  const [direction, setDirection] = useState<number | null>(null);
  const [selectedSubjects, setSelectedSubjects] = useState<number[]>([]);
  const [examDate, setExamDate] = useState("");
  const [minutes, setMinutes] = useState(60);
  const [level, setLevel] = useState<OnboardingLevel>("beginner");

  useEffect(() => {
    if (!user) return;
    let ignore = false;
    Promise.all([fetchOnboardingStatus(), fetchDirections(), fetchSubjects()])
      .then(([s, d, sub]) => {
        if (ignore) return;
        setStatus(s);
        setDirections(d);
        setSubjects(sub);
        // Re-running the wizard from /profile prefills the previous answers.
        setDirection(s.profile.direction?.id ?? null);
        setSelectedSubjects(s.profile.subjects.map((x) => x.id));
        setExamDate(s.profile.exam_date ?? "");
        setMinutes(s.profile.daily_minutes);
        setLevel(s.profile.level);
      })
      .catch(() => {
        if (!ignore) setLoadError(true);
      });
    return () => {
      ignore = true;
    };
  }, [user]);

  const toggleSubject = (id: number) =>
    setSelectedSubjects((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );

  const canNext =
    step === 1 ? true : step === 2 ? selectedSubjects.length > 0 : minutes >= MIN_DAILY_MINUTES && minutes <= MAX_DAILY_MINUTES;

  const submit = async () => {
    setPending(true);
    setSubmitError(null);
    try {
      const created = await submitOnboarding({
        direction,
        subjects: selectedSubjects,
        exam_date: examDate || null,
        daily_minutes: minutes,
        level,
      });
      setPlan(created);
      setStatus((s) =>
        s
          ? {
              ...s,
              completed: true,
              skipped: false,
              needs_onboarding: false,
              has_plan: true,
              profile: created.profile,
            }
          : s
      );
      // Release the auth gate so the student can leave the wizard.
      await recheckOnboarding();
    } catch (err) {
      setSubmitError(
        err instanceof ApiError
          ? extractFieldError(err.detail) ?? t("submitError")
          : t("submitError")
      );
    } finally {
      setPending(false);
    }
  };

  const skip = async () => {
    setPending(true);
    setSubmitError(null);
    try {
      await skipOnboarding();
      await recheckOnboarding();
      router.replace("/dashboard");
    } catch {
      setSubmitError(t("submitError"));
    } finally {
      setPending(false);
    }
  };

  if (plan) {
    return (
      <>
        <Header />
        <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-10 sm:px-6">
          <PlanResult plan={plan} />
        </main>
        <Footer />
      </>
    );
  }

  return (
    <>
      <Header />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-subtle">{t("subtitle")}</p>
        </div>

        <Progress step={step} />

        {loadError ? (
          <Alert variant="danger">
            <span className="flex flex-wrap items-center justify-between gap-3">
              {t("loadError")}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => window.location.reload()}
              >
                {common("retry")}
              </Button>
            </span>
          </Alert>
        ) : null}

        {submitError ? <Alert variant="danger">{submitError}</Alert> : null}

        {!status || loadError || authLoading ? (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-64 w-full rounded-2xl" />
          </div>
        ) : (
          <div className="card flex flex-col gap-6 p-5 sm:p-7">
            {step === 1 ? (
              <DirectionStep
                directions={directions}
                selected={direction}
                onSelect={setDirection}
              />
            ) : null}
            {step === 2 ? (
              <SubjectsStep
                subjects={subjects}
                selected={selectedSubjects}
                onToggle={toggleSubject}
                examDate={examDate}
                onExamDate={setExamDate}
              />
            ) : null}
            {step === 3 ? (
              <EffortStep
                minutes={minutes}
                onMinutes={setMinutes}
                level={level}
                onLevel={setLevel}
              />
            ) : null}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
              <button
                type="button"
                onClick={skip}
                disabled={pending}
                className="text-sm font-semibold text-subtle hover:underline"
              >
                {t("skip")}
              </button>
              <div className="flex items-center gap-2">
                {step > 1 ? (
                  <Button
                    variant="secondary"
                    disabled={pending}
                    onClick={() => setStep((s) => s - 1)}
                  >
                    {common("back")}
                  </Button>
                ) : null}
                {step < 3 ? (
                  <Button disabled={!canNext} onClick={() => setStep((s) => s + 1)}>
                    {common("next")}
                  </Button>
                ) : (
                  <Button disabled={!canNext || pending} onClick={submit}>
                    {pending ? common("loading") : t("generate")}
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}
