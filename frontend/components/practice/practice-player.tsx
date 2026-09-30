"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Paywall } from "@/components/premium/paywall";
import { fetchSubject } from "@/lib/catalog";
import { ApiError } from "@/lib/api";
import type { PracticeSession } from "@/lib/sessions";
import {
  fetchCurrent,
  finishSession,
  startPractice,
  submitAnswer,
  type AnswerResult,
  type NewBadge,
  type SessionOption,
  type SessionQuestion,
} from "@/lib/sessions";
import { cn } from "@/lib/utils";

type LocalizedText = {
  text_uz?: string;
  text_ru?: string;
  text_en?: string;
  explanation_uz?: string;
  explanation_ru?: string;
  explanation_en?: string;
};

function localText(item: LocalizedText, locale: string): string {
  // `||`, not `??`: the API returns "" (not null) for missing translations,
  // so `??` showed blank questions in ru/en.
  if (locale === "ru")
    return item.text_ru || item.text_uz || item.explanation_ru || "";
  if (locale === "en")
    return item.text_en || item.text_uz || item.explanation_en || "";
  return item.text_uz || item.explanation_uz || "";
}

function shuffleOptions(options: SessionOption[]): SessionOption[] {
  return [...options]
    .map((o) => ({ o, r: Math.random() }))
    .sort((a, b) => a.r - b.r)
    .map((x) => x.o);
}

function optionLabel(n: number): string {
  return String.fromCharCode(65 + n);
}

function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function CrossIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function Flame({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M15.5 11c0-1.5-.7-2.7-1.6-4 .3 1.6-.4 3-1.9 4-1.4 1-2.5 2.3-2.5 4.1A4 4 0 0 0 13.6 19c2.6 0 4.4-2 4.4-4.4 0-1.6-.7-2.8-2.5-3.6zM12 3a2 2 0 1 0-4 0 2 2 0 0 0 4 0z" />
    </svg>
  );
}

export function PracticePlayer({
  slug,
  questionIds,
  topicSlug,
  questionCount,
  startSession,
}: {
  slug?: string;
  questionIds?: number[];
  topicSlug?: string;
  questionCount?: number;
  /**
   * Custom session factory (weak-skill radar). When provided it replaces the
   * built-in starters, so a feature can create a session through its own
   * endpoint and still reuse this player instead of writing a second one.
   */
  startSession?: () => Promise<PracticeSession>;
}) {
  const t = useTranslations("common");
  const exam = useTranslations("exam");
  const res = useTranslations("results");
  const gam = useTranslations("gamification");
  const mis = useTranslations("mistakes");
  const locale = useLocale();
  const { user } = useAuth();
  const router = useRouter();
  // Mistakes notebook mode: drill an exact question list instead of sampling a subject.
  const mistakesMode = (questionIds?.length ?? 0) > 0;

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [question, setQuestion] = useState<SessionQuestion | null>(null);
  const [shuffled, setShuffled] = useState<SessionOption[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  // The session (and the daily free quota) is only created on an explicit
  // Start click вЂ” merely opening the page must not burn a session.
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fatal, setFatal] = useState(false);
  const [paywall, setPaywall] = useState(false);
  const [newBadges, setNewBadges] = useState<NewBadge[]>([]);
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const [progress, setProgress] = useState({ answered: 0, total: 0 });
  const [score, setScore] = useState<number | null>(null);
  const [correctTotal, setCorrectTotal] = useState(0);
  const [streak, setStreak] = useState(0);
  const [time, setTime] = useState({ correct: 0, wrong: 0 });
  // Latches so Enter+click cannot submit or advance twice (a second finish
  // call would 409 on an already-finished session).
  const answering = useRef(false);
  const advancing = useRef(false);

  // A custom starter (weak-skill radar) keeps its own page as the way back.
  const homeLink = startSession
    ? "/weak-skills"
    : mistakesMode
      ? "/mistakes"
      : `/subjects/${slug}`;
  const subjectLink = homeLink;
  // Where "start" sends guests and where the finish card sends the student.
  const pageLink = startSession ? "/weak-skills" : mistakesMode ? "/mistakes" : `/subjects/${slug}/practice`;

  useEffect(() => {
    if (!user || !started) return;
    let ignore = false;
    const start$ = startSession
      ? startSession()
      : mistakesMode
        ? startPractice({ mode: "practice", question_ids: questionIds })
        : fetchSubject(slug ?? "").then((subject) => {
          const topic = topicSlug
            ? subject.topics.find((t) => t.slug === topicSlug)
            : undefined;
          return startPractice({
            subject: subject.id,
            topic: topic?.id,
            question_count: questionCount ?? 10,
            mode: "practice",
          });
        });
    start$
      .then((sess) => {
        if (ignore) return;
        setSessionId(sess.id);
        setProgress({ answered: 0, total: sess.question_count });
        if (sess.current_question) {
          setQuestion(sess.current_question);
          setShuffled(shuffleOptions(sess.current_question.options));
        }
      })
      .catch((e) => {
        if (ignore) return;
        if (e instanceof ApiError && e.status === 402) {
          // Daily free limit reached вЂ” a plan is needed, retrying won't help.
          setPaywall(true);
          return;
        }
        // Nothing can be shown without a session: this one really is fatal.
        setError(t("error"));
        setFatal(true);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, slug, topicSlug, questionCount, started]);

  const answer = () => {
    if (!sessionId || !question || selected === null || answering.current) return;
    answering.current = true;
    submitAnswer(sessionId, question.id, selected)
      .then((r) => {
        setResult(r);
        setError(null);
        setRetry(null);
        setProgress((p) => ({ ...p, answered: p.answered + 1 }));
        setCorrectTotal((c) => c + (r.is_correct ? 1 : 0));
        setStreak((s) => (r.is_correct ? s + 1 : 0));
        setTime((x) => (r.is_correct ? { ...x, correct: x.correct + 1 } : { ...x, wrong: x.wrong + 1 }));
      })
      .catch(() => {
        // Recoverable: keep the question and the selection so the student can
        // just press the button again.
        setError(t("error"));
        setRetry(answer);
      })
      .finally(() => {
        answering.current = false;
      });
  };

  const next = () => {
    if (!sessionId || advancing.current) return;
    advancing.current = true;
    setSelected(null);
    setResult(null);
    setQuestion(null);
    setLoading(true);
    fetchCurrent(sessionId)
      .then((resQ) => {
        setError(null);
        setRetry(null);
        if (resQ.question) {
          setQuestion(resQ.question);
          setShuffled(shuffleOptions(resQ.question.options));
        } else {
          return finishSession(sessionId).then((rep) => {
            setScore(rep.score_percent);
            setCorrectTotal(rep.correct_answers);
            setProgress({ answered: rep.question_count, total: rep.question_count });
            setNewBadges(rep.new_badges ?? []);
          });
        }
      })
      .catch(() => {
        setError(t("error"));
        setRetry(next);
      })
      .finally(() => {
        advancing.current = false;
        setLoading(false);
      });
  };

  // Keyboard shortcuts: A-D/1-4 select, Enter submits / advances
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (score !== null) return;
      if (result) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          next();
        }
        return;
      }
      const k = e.key.toUpperCase();
      const idx = ["A", "B", "C", "D", "E", "F"].indexOf(k);
      if (idx >= 0 && idx < shuffled.length) {
        e.preventDefault();
        setSelected(shuffled[idx].id);
        return;
      }
      if (e.key === "Enter" && selected !== null) {
        e.preventDefault();
        answer();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shuffled, selected, result, score]);

  const optionState = (opt: SessionOption) => {
    if (!result) return "idle";
    if (opt.id === result.correct_option_id) return "correct";
    if (opt.id === selected) return "wrong";
    return "idle";
  };

  return (
    <ProtectedShell>
      <div className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6">
        {/* Topbar */}
        <div className="mb-5 flex items-center justify-between gap-3">
          <Link href={subjectLink} className="btn btn-ghost btn-sm">
            в†ђ {t("back")}
          </Link>
          <div className="flex items-center gap-3">
            {streak >= 2 ? (
              <span className="badge badge-warning gap-1 px-2.5 py-1">
                <Flame />
                {streak}
              </span>
            ) : null}
            <span className="text-sm font-semibold tabular-nums text-muted">
              {progress.answered} / {progress.total}
            </span>
          </div>
        </div>

        {/* Segment progress */}
        <div className="mb-6 flex h-2 w-full gap-1 overflow-hidden">
          {Array.from({ length: progress.total }).map((_, i) => (
            <span
              key={i}
              className={cn(
                "h-full flex-1 rounded-full transition-colors duration-300",
                i < progress.answered ? "bg-primary" : "bg-surface-subtle"
              )}
            />
          ))}
        </div>

        {paywall ? (
          <Paywall onBack={() => window.history.back()} backLabel={t("back")} />
        ) : fatal ? (
          <div className="card flex flex-col items-center gap-4 p-10 text-center">
            <p className="text-muted">{error}</p>
            <Link href={subjectLink} className="btn btn-secondary btn-sm">
              {t("back")}
            </Link>
          </div>
        ) : !started ? (
          /* Landing card вЂ” the session (and daily quota) is only created
             when the student explicitly starts. */
          <Card className="pop flex flex-col items-center gap-5 p-10 text-center">
            <span className="badge badge-primary">DTM</span>
            <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
              {mistakesMode ? mis("startTitle") : exam("practiceTitle")}
            </h2>
            <p className="max-w-md font-serif italic text-muted">
              {mistakesMode
                ? mis("startNotice", { count: questionIds?.length ?? 0 })
                : exam("startNotice")}
            </p>
            <Button
              onClick={() => {
                // Guests can preview this page (public prefix) but a session
                // needs an account вЂ” send them to login instead of a spinner.
                if (!user) {
                  router.replace(`/login?next=${encodeURIComponent(pageLink)}`);
                  return;
                }
                setLoading(true);
                setStarted(true);
              }}
              className="btn-lg px-10"
            >
              {exam("start")}
            </Button>
            <Link href={subjectLink} className="text-sm font-semibold text-primary hover:underline">
              {t("back")}
            </Link>
          </Card>
        ) : (
          <>
            {error && !fatal ? (
              <div
                role="alert"
                className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
              >
                <span>{error}</span>
                <span className="flex items-center gap-2">
                  {retry ? (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setError(null);
                        setRetry(null);
                        retry();
                      }}
                      disabled={loading}
                    >
                      {t("retry")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setError(null);
                      setRetry(null);
                    }}
                  >
                    {t("cancel")}
                  </button>
                </span>
              </div>
            ) : null}

            {loading ? (
              <div className="flex flex-col gap-4">
                <Skeleton className="h-24" />
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            ) : score !== null ? (
              /* Finish вЂ” score ring + summary (Quizzler-style) */
              <Card className="pop flex flex-col items-center gap-6 p-10 text-center">
                <div
                  className="relative h-36 w-36"
                  style={{ "--p": score } as React.CSSProperties}
                  role="progressbar"
                  aria-valuenow={score}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={exam("resultsSummary")}
                >
                  <div className="score-ring absolute inset-0" />
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-4xl font-bold tabular-nums">{score}%</span>
                    <span className="text-xs font-medium text-muted">{exam("resultsSummary")}</span>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-2 rounded-xl bg-success-soft px-4 py-2.5">
                    <CheckIcon />
                    <span className="text-sm font-semibold text-success">
                      {time.correct || correctTotal} {res("correct").toLowerCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 rounded-xl bg-danger-soft px-4 py-2.5">
                    <CrossIcon />
                    <span className="text-sm font-semibold text-danger">
                      {time.wrong} {res("incorrect").toLowerCase()}
                    </span>
                  </div>
                </div>
                {newBadges.length ? (
                  <div className="flex flex-wrap items-center justify-center gap-2">
                    <span className="badge badge-warning">{gam("newBadge")}</span>
                    {newBadges.map((b) => (
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
                <div className="flex w-full max-w-sm flex-col gap-3 sm:flex-row">
                  {mistakesMode ? null : (
                    <Link href={`/subjects/${slug}/practice`} className="btn btn-secondary btn-lg flex-1">
                      {t("again")}
                    </Link>
                  )}
                  <Link href={`/results/${sessionId}`} className="btn btn-secondary btn-lg flex-1">
                    {res("viewDetailed")}
                  </Link>
                  <Link href={subjectLink} className="btn btn-primary btn-lg flex-1">
                    {t("back")}
                  </Link>
                </div>
              </Card>
            ) : question ? (
          <div className="flex flex-col gap-4">
            <Card className="p-6">
              <p className="text-lg font-medium leading-relaxed">{localText(question, locale)}</p>
            </Card>

            <div className="flex flex-col gap-2.5">
              {shuffled.map((opt, i) => {
                const state = optionState(opt);
                const isSelected = state === "idle" && selected === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    disabled={!!result}
                    onClick={() => setSelected(opt.id)}
                    className={cn(
                      "group flex items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition-all sm:px-4",
                      state === "idle" &&
                        isSelected &&
                        "border-primary bg-primary-soft shadow-popover",
                      state === "idle" &&
                        !isSelected &&
                        "border-border bg-surface hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised",
                      state === "correct" && "pop border-success bg-success-soft",
                      state === "wrong" && "pop border-danger bg-danger-soft",
                      "disabled:cursor-default disabled:opacity-100"
                    )}
                  >
                    <span
                      className={cn(
                        "option-key",
                        state === "correct" && "bg-success text-white",
                        state === "wrong" && "bg-danger text-white",
                        state === "idle" && isSelected && "bg-primary text-white",
                        state === "idle" && !isSelected && "bg-surface-subtle text-muted group-hover:bg-primary-muted"
                      )}
                    >
                      {optionLabel(i)}
                    </span>
                    <span className="flex-1 text-sm font-medium">{localText(opt, locale)}</span>
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
              })}
            </div>

            <div className="mt-2 flex items-center justify-between text-xs text-subtle">
              <span>{t("keyboardHints")}</span>
              {selected !== null && !result ? <span className="text-primary">{t("pressEnter")}</span> : null}
            </div>

            {result ? (
              <Card
                className={cn(
                  "pop flex flex-col gap-2 p-5",
                  result.is_correct ? "border-success" : "border-danger"
                )}
              >
                <p
                  className={cn(
                    "flex items-center gap-2 text-lg font-bold",
                    result.is_correct ? "text-success" : "text-danger"
                  )}
                >
                  {result.is_correct ? <CheckIcon /> : <CrossIcon />}
                  {result.is_correct ? exam("correctAnswer") : exam("wrongAnswer")}
                </p>
                {localText(result, locale) ? (
                  <p className="text-sm leading-relaxed text-muted">
                    <span className="font-semibold">{exam("explanation")}: </span>
                    {localText(result, locale)}
                  </p>
                ) : null}
              </Card>
            ) : null}

            {!result ? (
              <Button onClick={answer} disabled={selected === null} className="mt-1">
                {exam("submitAnswer")}
                {selected !== null ? <span className="opacity-70">в†µ</span> : null}
              </Button>
            ) : (
              <Button variant={result.is_correct ? "primary" : "secondary"} onClick={next} className="mt-1">
                {progress.answered >= progress.total ? exam("finish") : t("next")}
                <span className="opacity-70">в†µ</span>
              </Button>
            )}
          </div>
        ) : (
          <div className="card flex flex-col items-center gap-4 p-10 text-center">
            <p className="text-muted">{t("empty")}</p>
            <Link href={subjectLink} className="btn btn-secondary btn-sm">
              {t("back")}
            </Link>
          </div>
        )}
          </>
        )}
      </div>
    </ProtectedShell>
  );
}