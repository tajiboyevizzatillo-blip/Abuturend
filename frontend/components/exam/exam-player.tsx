"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { startPractice, fetchSessionQuestions, submitAnswer, finishSession, type SessionQuestion, type SessionReport, type SessionOption } from "@/lib/sessions";
import { createCertificate, type CertificateStyle } from "@/lib/certificates";
import { ApiError, extractFieldError } from "@/lib/api";
import { localizedName, type Subject } from "@/lib/catalog";
import { Paywall } from "@/components/premium/paywall";
import { ReportList } from "@/components/report/report-list";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const detail = extractFieldError(e.detail);
    return detail ?? fallback;
  }
  return fallback;
}

function CheckIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function CrossIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function ClockIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}

interface ExamSetupProps {
  subjects: Subject[];
  onStart: (subject: Subject | null, questionCount: number, minutes: number) => void;
  onHistory: () => void;
}

export function ExamSetup({ subjects, onStart, onHistory }: ExamSetupProps) {
  const t = useTranslations("exam");
  const common = useTranslations("common");
  const locale = useLocale();

  // null subject = the unified exam (umumiy imtihon) across every subject.
  const [subject, setSubject] = useState<Subject | null>(null);
  const [unified, setUnified] = useState(false);
  const [count, setCount] = useState(10);
  const [minutes, setMinutes] = useState(10);

  const ready = unified || subject !== null;

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
      <div className="flex flex-col items-center gap-2 text-center">
        <span className="badge badge-primary">DTM</span>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{t("title")}</h1>
        <p className="font-serif italic text-subtle">{t("chooseSubject")}</p>
      </div>

      <button
        type="button"
        onClick={() => {
          setUnified(true);
          setSubject(null);
        }}
        className={cn(
          "card card-hover flex items-center gap-3 p-4 text-left",
          unified && "border-primary/50 bg-primary-soft"
        )}
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal text-sm font-bold text-white">
          🎓
        </span>
        <span className="flex flex-col">
          <span className="font-semibold">{t("unifiedTitle")}</span>
          <span className="text-xs text-subtle">{t("unifiedDesc")}</span>
        </span>
        {unified ? (
          <span className="ml-auto text-primary">
            <CheckIcon />
          </span>
        ) : null}
      </button>

      <div className="grid gap-3 sm:grid-cols-2">
        {subjects.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => {
              setUnified(false);
              setSubject(s);
            }}
            className={cn(
              "card card-hover flex items-center gap-3 p-4 text-left",
              !unified && subject?.id === s.id && "border-primary/50 bg-primary-soft"
            )}
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-navy text-sm font-bold text-primary-foreground">
              {(s.code || localizedName(s, locale).charAt(0)).toUpperCase()}
            </span>
            <span className="font-semibold">{localizedName(s, locale)}</span>
            {!unified && subject?.id === s.id ? (
              <span className="ml-auto text-primary">
                <CheckIcon />
              </span>
            ) : null}
          </button>
        ))}
      </div>

      <div className="card flex flex-col gap-5 p-6">
        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold text-subtle">{t("questionCount")}</span>
          <div className="grid grid-cols-3 gap-3">
            {[5, 10, 15].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => {
                  setCount(n);
                  setMinutes(n);
                }}
                className={cn(
                  "segment-option",
                  count === n && "segment-option-active"
                )}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold text-subtle">{t("timeLimitMin")}</span>
          <div className="grid grid-cols-3 gap-3">
            {[5, 10, 15].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMinutes(m)}
                className={cn(
                  "segment-option",
                  minutes === m && "segment-option-active"
                )}
              >
                {m} {common("minUnit")}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          disabled={!ready}
          className="btn btn-primary btn-lg w-full"
          onClick={() => ready && onStart(unified ? null : subject, count, minutes)}
        >
          {t("startExam")}
        </button>

        <button
          type="button"
          className="text-sm font-medium text-subtle underline-offset-4 hover:text-primary hover:underline"
          onClick={onHistory}
        >
          {t("history")}
        </button>
      </div>
    </div>
  );
}

function OptionRow({
  option,
  state,
  selected,
  onSelect,
}: {
  option: SessionOption;
  state: "default" | "correct" | "wrong";
  selected: boolean;
  onSelect: () => void;
}) {
  const locale = useLocale();
  const isRevealed = state !== "default";
  const text =
    locale === "ru"
      ? option.text_ru || option.text_uz
      : locale === "en"
        ? option.text_en || option.text_uz
        : option.text_uz;
  const letter = String.fromCharCode(65 + option.sort_order);
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={isRevealed && !selected}
      className={cn(
        "option-card",
        selected && !isRevealed && "option-card-selected",
        state === "correct" && "option-card-correct",
        state === "wrong" && "option-card-wrong"
      )}
    >
      <span
        className={cn(
          "option-key",
          state === "correct" && "bg-success text-white",
          state === "wrong" && "bg-danger text-white",
          selected && !isRevealed && "bg-primary text-white",
          !selected && !isRevealed && "bg-surface-subtle text-muted"
        )}
      >
        {letter}
      </span>
      <span className="flex-1 text-left text-sm font-medium">{text}</span>
      {state === "correct" ? (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-success text-white">
          <CheckIcon />
        </span>
      ) : state === "wrong" ? (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-danger text-white">
          <CrossIcon />
        </span>
      ) : null}
    </button>
  );
}

function TimerBadge({ remaining }: { remaining: number }) {
  const t = useTranslations("exam");
  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");
  const danger = remaining <= 300;
  const warn = remaining <= 600 || danger;
  return (
    <span className={cn("badge", danger ? "badge-danger pulse" : warn ? "badge-warning" : "badge-neutral")}>
      <ClockIcon />
      {t("timeRemaining")}: {mm}:{ss}
    </span>
  );
}

export function ExamPlayer({
  subject,
  questionCount,
  minutes,
  onExit,
}: {
  // null = unified exam (umumiy imtihon) across all subjects.
  subject: Subject | null;
  questionCount: number;
  minutes: number;
  onExit: () => void;
}) {
  const t = useTranslations("exam");
  const common = useTranslations("common");
  const gam = useTranslations("gamification");
  const locale = useLocale();
  const router = useRouter();

  // The server owns the deadline (deadline_at); the client countdown is only
  // a display. Initialize locally so the clock ticks before the session
  // payload arrives, then re-sync to the server value.
  const [deadline, setDeadline] = useState(() => Date.now() + minutes * 60 * 1000);
  const [remaining, setRemaining] = useState(minutes * 60);
  const [timeExpired, setTimeExpired] = useState(false);

  const [questions, setQuestions] = useState<SessionQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [selected, setSelected] = useState<Record<number, number>>({});
  const [index, setIndex] = useState(0);
  const [finished, setFinished] = useState(false);
  const [report, setReport] = useState<SessionReport | null>(null);
  const [pending, setPending] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [paywall, setPaywall] = useState(false);
  const [finishFailed, setFinishFailed] = useState(false);
  const [certStyle, setCertStyle] = useState<CertificateStyle | null>(null);
  const [certError, setCertError] = useState<string | null>(null);

  const sessionId = useRef<number | null>(null);
  const finishing = useRef(false);
  const autoFinished = useRef(false);

  const issueCertificate = async (style: CertificateStyle) => {
    if (!report || certStyle) return;
    setCertStyle(style);
    setCertError(null);
    try {
      const cert = await createCertificate(report.id, style);
      router.push(`/verify/${cert.serial}`);
    } catch (e) {
      setCertStyle(null);
      setCertError(errorMessage(e, common("error")));
    }
  };

  const finish = useCallback(async () => {
    if (finished || !sessionId.current || finishing.current) return;
    finishing.current = true;
    setSubmitting(true);
    setFinishFailed(false);
    try {
      const rep = await finishSession(sessionId.current);
      setReport(rep);
      setFinished(true);
      setError(null);
    } catch (e) {
      // A failed finish must stay retryable: clearing the guard lets the student
      // press finish again instead of being stuck with a dead session.
      finishing.current = false;
      setFinishFailed(true);
      setError(errorMessage(e, common("error")));
    } finally {
      setSubmitting(false);
    }
  }, [finished, common]);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const session = await startPractice({
          subject: subject?.id ?? null,
          question_count: questionCount,
          mode: "exam",
          duration_minutes: minutes,
        });
        sessionId.current = session.id;
        if (session.deadline_at && !ignore) {
          const serverDeadline = Date.parse(session.deadline_at);
          if (!Number.isNaN(serverDeadline)) setDeadline(serverDeadline);
        }
        const qs = await fetchSessionQuestions(session.id);
        if (!ignore) {
          setQuestions(qs);
          setPending(false);
        }
      } catch (e) {
        if (!ignore) {
          // 402 = the free daily limit is gone; the student needs a plan, not a retry.
          if (e instanceof ApiError && e.status === 402) {
            setPaywall(true);
          } else {
            setError(errorMessage(e, common("error")));
            setLoadFailed(true);
          }
          setPending(false);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, [subject?.id, questionCount, minutes, common]);

  useEffect(() => {
    const interval = setInterval(() => {
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setRemaining(left);
      // Fire the auto-finish once. Without the latch a failing request would be
      // retried every second for as long as the tab stays open.
      if (left === 0 && !autoFinished.current) {
        autoFinished.current = true;
        finish();
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [finish, deadline]);

  const question = questions[index];

  const submitCurrent = async () => {
    const optId = selected[question.id];
    if (optId == null || !sessionId.current || submitting) return;
    setSubmitting(true);
    try {
      await submitAnswer(sessionId.current, question.id, optId);
      setAnswers((prev) => ({ ...prev, [question.id]: optId }));
      setError(null);
      if (!(index + 1 < questions.length)) {
        finish();
      } else {
        setIndex((i) => i + 1);
        setSubmitting(false);
      }
    } catch (e) {
      // Server-side deadline hit: finish rather than showing a dead-end error.
      if (e instanceof ApiError && e.status === 409 && (e.detail as { time_expired?: boolean } | null)?.time_expired) {
        setTimeExpired(true);
        setSubmitting(false);
        finish();
        return;
      }
      // Keep the question on screen: a failed submit is recoverable.
      setError(errorMessage(e, common("error")));
      setSubmitting(false);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (finished) return;
      if (question && e.key >= "1" && e.key <= "9") {
        const idx = Number(e.key) - 1;
        const opt = question.options[idx];
        if (opt) setSelected((prev) => ({ ...prev, [question.id]: opt.id }));
      } else if (e.key === "Enter" && question) {
        e.preventDefault();
        submitCurrent();
      } else if (e.key >= "a" && e.key <= "z") {
        const idx = e.key.charCodeAt(0) - 97;
        const opt = question?.options[idx];
        if (opt) setSelected((prev) => ({ ...prev, [question.id]: opt.id }));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const answeredCount = Object.keys(answers).length;

  const questionLocal = (q: SessionQuestion) =>
    locale === "ru" ? q.text_ru || q.text_uz : locale === "en" ? q.text_en || q.text_uz : q.text_uz;

  if (finished) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="card relative flex flex-col items-center gap-4 overflow-hidden p-8 text-center">
          <div aria-hidden className="pointer-events-none absolute -right-14 -top-14 h-40 w-40 rounded-full bg-teal/20 blur-3xl" />
          {timeExpired || remaining === 0 ? (
            <span className="badge badge-success">✓ {t("autoFinishNotice")}</span>
          ) : (
            <span className="badge badge-success">✓ {t("resultsSummary")}</span>
          )}
          <div
            className="score-ring score-ring-lg"
            role="progressbar"
            aria-valuenow={report?.score_percent ?? 0}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t("resultsSummary")}
          >
            <span className="text-2xl font-bold tabular-nums">{report?.score_percent ?? 0}%</span>
          </div>
          <p className="text-lg font-semibold">{t("resultsSummary")}</p>
          <div className="flex items-center gap-3">
            <span className="badge badge-success" title={t("correctAnswer")}>{report?.correct_answers ?? 0} ✓</span>
            <span className="badge badge-danger" title={t("wrongAnswer")}>{report?.incorrect_answers ?? 0} ✕</span>
            <span className="badge badge-neutral">{report?.unanswered ?? 0} —</span>
          </div>
          {report?.new_badges?.length ? (
            <div className="flex flex-wrap items-center justify-center gap-2">
              <span className="badge badge-warning">{gam("newBadge")}</span>
              {report.new_badges.map((b) => (
                <span key={b.code} className="badge badge-warning">
                  {locale === "ru"
                    ? b.name_ru || b.name_uz
                    : locale === "en"
                      ? b.name_en || b.name_uz
                      : b.name_uz}
                </span>
              ))}
            </div>
          ) : null}
          {report?.unified ? (
            <div className="flex w-full flex-col gap-2 rounded-xl border border-border bg-surface-subtle/60 p-4">
              <span className="text-sm font-semibold text-subtle">{t("certTitle")}</span>
              <div className="flex flex-wrap justify-center gap-3">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={certStyle !== null}
                  onClick={() => issueCertificate("international")}
                >
                  {certStyle === "international" ? common("loading") : t("certInternational")}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={certStyle !== null}
                  onClick={() => issueCertificate("local")}
                >
                  {certStyle === "local" ? common("loading") : t("certLocal")}
                </button>
              </div>
              {certError ? (
                <p role="alert" className="text-sm text-danger">{certError}</p>
              ) : null}
            </div>
          ) : null}
          <div className="flex gap-3">
            <button type="button" className="btn btn-secondary" onClick={onExit}>
              {t("history")}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => window.location.reload()}
            >
              {t("startExam")}
            </button>
          </div>
        </div>
        <ReportList report={report} />
      </div>
    );
  }

  if (pending) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-5 px-4 py-8 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-6 w-32 rounded-full" />
        </div>
        <div className="flex gap-1.5">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <Skeleton key={i} className="h-2 flex-1 rounded-full" />
          ))}
        </div>
        <Skeleton className="h-4 w-52" />
        <Skeleton className="h-56 rounded-3xl" />
        <Skeleton className="h-12 w-full rounded-xl" />
      </div>
    );
  }

  if (paywall) {
    return <Paywall onBack={onExit} backLabel={common("back")} />;
  }

  if (loadFailed) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center gap-4 px-4">
        <span className="text-danger">{error ?? common("error")}</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onExit}>
          {common("back")}
        </button>
      </div>
    );
  }

  if (!question) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center gap-4 px-4">
        <span className="text-muted">{t("notStarted")}</span>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-5 px-4 py-8 sm:px-6">
      <div className="flex items-center justify-between gap-3">
        <button type="button" className="btn btn-secondary btn-sm" onClick={onExit}>
          {common("cancel")}
        </button>
        <TimerBadge remaining={remaining} />
      </div>

      {error ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          <span>{error}</span>
          <span className="flex items-center gap-2">
            {finishFailed ? (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={finish}
                disabled={submitting}
              >
                {common("retry")}
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setError(null)}
            >
              {common("cancel")}
            </button>
          </span>
        </div>
      ) : null}

      {/* progress segments */}
      <div className="flex gap-1.5">
        {questions.map((q, i) => (
          <button
            key={q.id}
            type="button"
            onClick={() => setIndex(i)}
            aria-label={`${t("question")} ${i + 1}`}
            className={cn(
              "h-2 flex-1 rounded-full transition-colors",
              answers[q.id] != null
                ? "bg-navy"
                : i === index
                  ? "bg-primary"
                  : "bg-surface-subtle"
            )}
          />
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-subtle">
          {t("question")} {index + 1} {common("of")} {questions.length}
        </span>
        <span className="text-sm font-medium text-subtle">
          {answeredCount}/{questions.length} {t("answered")}
        </span>
      </div>

      <div className="card flex flex-col gap-4 p-6">
        <h2 className="text-lg font-semibold leading-relaxed">{questionLocal(question)}</h2>
        <div className="flex flex-col gap-2.5">
          {question.options.map((opt) => (
            <OptionRow
              key={opt.id}
              option={opt}
              selected={selected[question.id] === opt.id}
              state="default"
              onSelect={() =>
                setSelected((prev) => ({ ...prev, [question.id]: opt.id }))
              }
            />
          ))}
        </div>
        <button
          type="button"
          className={cn("btn btn-primary w-full", !selected[question.id] && "btn-disabled")}
          onClick={submitCurrent}
          disabled={submitting}
        >
          {index + 1 < questions.length ? common("next") : t("finish")}
        </button>
        <p className="text-center text-xs text-subtle">{common("keyboardHints")}</p>
      </div>
    </div>
  );
}