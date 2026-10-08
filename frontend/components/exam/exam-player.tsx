"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { startPractice, fetchSessionQuestions, submitAnswer, finishSession, abandonSession, type SessionQuestion, type SessionReport, type SessionOption } from "@/lib/sessions";
import { createCertificate, type CertificateStyle } from "@/lib/certificates";
import { ApiError, extractFieldError } from "@/lib/api";
import { localizedName, type Subject } from "@/lib/catalog";
import { Paywall } from "@/components/premium/paywall";
import { ReportList } from "@/components/report/report-list";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/providers/auth-provider";
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
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

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
                  // The chosen time limit is deliberate: only the default
                  // pairing (10 questions / 10 min) is set up front, so picking
                  // a different count must not silently reset the duration.
                  setCount(n);
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
          disabled={!ready || authLoading}
          className="btn btn-primary btn-lg w-full"
          onClick={() => {
            if (!ready) return;
            // Guests can preview /mock-exams (public prefix), but starting a
            // session needs an account — send them to login instead of letting
            // the API answer an unexplained 401.
            if (!user) {
              router.replace(`/login?next=${encodeURIComponent("/mock-exams")}`);
              return;
            }
            onStart(unified ? null : subject, count, minutes);
          }}
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

function TimerBadge({ remaining, total }: { remaining: number; total: number }) {
  const t = useTranslations("exam");
  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");
  // Proportional to the chosen length: absolute 5/10-minute cutoffs painted a
  // 5-minute exam red from the very first second while a 60-minute one stayed
  // calm far too long. Floors keep a short exam from flashing both states.
  const danger = remaining <= Math.max(30, Math.round(total * 0.1));
  const warn = remaining <= Math.max(60, Math.round(total * 0.25)) || danger;
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
  // Bumped by the retry button so the load effect re-runs without remounting
  // the whole player (which would throw the session away).
  const [loadAttempt, setLoadAttempt] = useState(0);
  // The last question asks for confirmation before scoring — the submit keys
  // already existed in i18n but nothing ever rendered them.
  const [confirming, setConfirming] = useState(false);
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
        // Retry must not create a second session (that would spend another
        // daily slot and orphan the first one): reuse the id when the start
        // call already succeeded and only the questions call failed.
        let id = sessionId.current;
        if (id == null) {
          const session = await startPractice({
            subject: subject?.id ?? null,
            question_count: questionCount,
            mode: "exam",
            duration_minutes: minutes,
          });
          id = session.id;
          sessionId.current = session.id;
          if (session.deadline_at) {
            const serverDeadline = Date.parse(session.deadline_at);
            if (!Number.isNaN(serverDeadline)) setDeadline(serverDeadline);
          }
        }
        const qs = await fetchSessionQuestions(id);
        if (!ignore) {
          setQuestions(qs);
          setPending(false);
          setLoadFailed(false);
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
    // Deliberately no unmount cleanup that abandons the session: a refresh or
    // a closed tab must not destroy an attempt the student may come back to.
    // The server finishes an expired exam lazily when the list is read (see
    // practice.views.expire_stale_sessions), so the row resolves itself.
  }, [subject?.id, questionCount, minutes, common, loadAttempt]);

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
    // Confirmation is showing: Enter (or the button) is the "yes, finish".
    if (confirming) {
      await finish();
      return;
    }
    const current = question;
    if (!current) return;
    const qid = current.id;
    const optId = selected[qid];
    if (optId == null || !sessionId.current || submitting) return;
    const isLast = index + 1 >= questions.length;
    const previous = answers[qid];

    // Already submitted and unchanged: nothing to send — advance, or ask
    // before scoring when the paper ends here.
    if (previous != null && previous === optId) {
      if (isLast) setConfirming(true);
      else setIndex((i) => Math.min(i + 1, questions.length - 1));
      return;
    }

    setSubmitting(true);
    try {
      await submitAnswer(sessionId.current, qid, optId);
      // Covers both the first answer and a changed one: the progress dots let
      // the student jump back, and the server accepts a replacement answer —
      // silently dropping it left the UI showing a selection the server never
      // recorded.
      setAnswers((prev) => ({ ...prev, [qid]: optId }));
      setError(null);
      setSubmitting(false);
      if (isLast) {
        setConfirming(true);
      } else {
        setIndex((i) => i + 1);
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

  // submitCurrent is recreated on every render (it closes over the current
  // question and index). Rather than depend on it — which would re-register the
  // listener on every one of the per-second countdown renders — the handler
  // calls the latest version through a ref kept in an effect.
  const submitRef = useRef(submitCurrent);
  useEffect(() => {
    submitRef.current = submitCurrent;
  });

  // Leaving mid-exam must tell the server, not just navigate away. Without it
  // the session stayed in_progress forever and appeared in the history list as
  // a row that led nowhere. Abandoning is not finishing: no score, no report,
  // no badges. The daily quota slot stays spent either way, since the questions
  // were already served.
  const [exiting, setExiting] = useState(false);
  const exit = useCallback(async () => {
    const id = sessionId.current;
    setExiting(true);
    if (id) {
      try {
        await abandonSession(id);
      } catch {
        // Abandoning is best-effort cleanup. If it fails the session stays
        // in_progress server-side, which is the pre-existing behaviour, so
        // navigating away is still better than trapping the student here.
      }
    }
    onExit();
  }, [onExit]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (finished) return;
      // Modifier combos belong to the browser (Ctrl+R, Ctrl+W, Cmd+…) — an
      // exam shortcut must never swallow them.
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const target = e.target;
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT")
      ) {
        return;
      }
      if (question && e.key >= "1" && e.key <= "9") {
        const idx = Number(e.key) - 1;
        const opt = question.options[idx];
        if (opt) {
          setConfirming(false);
          setSelected((prev) => ({ ...prev, [question.id]: opt.id }));
        }
      } else if (e.key === "Enter" && question) {
        // When focus sits on a real control, Enter must activate *that*
        // control (cancel, retry, confirm) instead of firing the shortcut.
        const active = document.activeElement;
        if (
          active instanceof HTMLButtonElement &&
          !active.classList.contains("option-card")
        ) {
          return;
        }
        e.preventDefault();
        submitRef.current();
      } else if (e.key >= "a" && e.key <= "z") {
        const idx = e.key.charCodeAt(0) - 97;
        const opt = question?.options[idx];
        if (opt) {
          setConfirming(false);
          setSelected((prev) => ({ ...prev, [question.id]: opt.id }));
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [finished, question]);

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
    return <Paywall onBack={exit} backLabel={common("back")} />;
  }

  if (loadFailed) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center gap-4 px-4">
        <span className="text-danger">{error ?? common("error")}</span>
        <div className="flex gap-3">
          {/* Retrying reuses an already-created session (see the load effect),
              so a transient network blip does not spend a second daily slot. */}
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => {
              setError(null);
              setPending(true);
              setLoadAttempt((k) => k + 1);
            }}
          >
            {common("retry")}
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={exit}>
            {common("back")}
          </button>
        </div>
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
        <button type="button" className="btn btn-secondary btn-sm" onClick={exit} disabled={exiting}>
          {common("cancel")}
        </button>
        <TimerBadge remaining={remaining} total={minutes * 60} />
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
            onClick={() => {
              setConfirming(false);
              setIndex(i);
            }}
            aria-label={`${t("question")} ${i + 1}`}
            // Announced so a screen reader reports the segment's state, not just
            // its position — the fill colour alone carries "answered".
            aria-current={i === index ? "step" : undefined}
            data-answered={answers[q.id] != null ? "true" : "false"}
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
              onSelect={() => {
                // Picking a different option withdraws the pending confirmation:
                // otherwise "yes, finish" would score the previous submission.
                setConfirming(false);
                setSelected((prev) => ({ ...prev, [question.id]: opt.id }));
              }}
            />
          ))}
        </div>
        {confirming ? (
          <div
            role="alertdialog"
            aria-label={t("submitConfirmTitle")}
            className="flex flex-col gap-3 rounded-xl border border-border bg-surface-subtle/60 p-4"
          >
            <div className="flex flex-col gap-1">
              <p className="font-semibold">{t("submitConfirmTitle")}</p>
              <p className="text-sm text-subtle">{t("submitConfirmText")}</p>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                className="btn btn-primary flex-1"
                onClick={finish}
                disabled={submitting}
              >
                {submitting ? common("loading") : t("submitYes")}
              </button>
              <button
                type="button"
                className="btn btn-secondary flex-1"
                onClick={() => setConfirming(false)}
                disabled={submitting}
              >
                {common("cancel")}
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className={cn(
              "btn btn-primary w-full",
              selected[question.id] == null && "btn-disabled"
            )}
            onClick={submitCurrent}
            disabled={submitting || selected[question.id] == null}
          >
            {/* The last question submits and then asks for confirmation;
                everywhere else the button advances. */}
            {index + 1 < questions.length ? common("next") : t("finish")}
          </button>
        )}
        <p className="text-center text-xs text-subtle">{common("keyboardHints")}</p>
      </div>
    </div>
  );
}