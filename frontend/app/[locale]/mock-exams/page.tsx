"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { ExamSetup, ExamPlayer } from "@/components/exam/exam-player";
import { fetchSubjects, localizedName, type Subject } from "@/lib/catalog";
import { fetchSessionList, type SessionListItem } from "@/lib/sessions";
import { cn } from "@/lib/utils";

function HistoryList({ subjects, onBack }: { subjects: Subject[]; onBack: () => void }) {
  const t = useTranslations("exam");
  const common = useTranslations("common");
  const locale = useLocale();
  const [rows, setRows] = useState<SessionListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchSessionList()
      .then((data) => setRows(data.filter((r) => r.mode === "exam")))
      .catch(() => setError(common("error")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const nameById = useMemo(
    () => new Map(subjects.map((s) => [s.id, localizedName(s, locale)])),
    [subjects, locale]
  );
  const subjectName = (id: number | null) =>
    id === null ? t("unifiedTitle") : nameById.get(id) ?? `#${id}`;

  return (
    <div className="mx-auto w-full max-w-2xl flex-1 px-4 py-8 sm:px-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-extrabold tracking-tight">{t("history")}</h1>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onBack}>
          {common("back")}
        </button>
      </div>

      {error ? <Alert variant="danger">{error}</Alert> : null}

      {!rows && !error ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : rows && rows.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 p-14 text-center">
          <p className="text-muted">{common("empty")}</p>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onBack}>
            {t("startExam")}
          </button>
        </div>
      ) : rows ? (
        <div className="flex flex-col gap-3">
          {rows.map((r) => (
            <div key={r.id} className="card card-hover flex items-center gap-4 p-5">
              <div
                className={cn(
                  "relative h-16 w-16 shrink-0",
                  r.status === "finished" && (r.score_percent ?? 0) >= 60 ? "text-success" : "text-danger"
                )}
              >
                <div
                  className="score-ring absolute inset-0"
                  style={{ "--p": r.score_percent ?? 0 } as React.CSSProperties}
                  role="progressbar"
                  aria-valuenow={r.score_percent ?? 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
                <div className="absolute inset-0 flex items-center justify-center text-sm font-bold tabular-nums">
                  {r.status === "finished" ? `${r.score_percent ?? 0}%` : "…"}
                </div>
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <p className="truncate font-semibold">{subjectName(r.subject?.id ?? null)}</p>
                <p className="text-xs text-subtle">
                  {new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(r.started_at))}
                </p>
                <div className="mt-1 flex gap-2">
                  <span className="badge badge-neutral">
                    {r.correct_answers ?? "…"}/{r.question_count} ✓
                  </span>
                  <span className="badge badge-neutral">
                    {r.correct_answers === null ? "…" : (r.incorrect_answers ?? 0) + r.unanswered} ✗
                  </span>
                </div>
              </div>
              <span className={cn("badge", r.status === "finished" ? "badge-success" : "badge-warning")}>
                {r.status === "finished" ? common("verified") : common("inProgress")}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function MockExamsPage() {
  const common = useTranslations("common");

  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"setup" | "player" | "history">("setup");
  const [active, setActive] = useState<{
    subject: Subject | null;
    questionCount: number;
    minutes: number;
    key: number;
  } | null>(null);

  useEffect(() => {
    let ignore = false;
    fetchSubjects()
      .then((data) => {
        if (!ignore) setSubjects(data);
      })
      .catch(() => {
        if (!ignore) setError(common("error"));
      });
    return () => {
      ignore = true;
    };
  }, [common]);

  return (
    <ProtectedShell>
      {view === "setup" ? (
        <>
          {!subjects && !error ? (
            <div className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6">
              <div className="flex flex-col gap-4">
                <Skeleton className="h-10" />
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-16" />
                ))}
              </div>
            </div>
          ) : error ? (
            <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center gap-4 px-4 py-20">
              <Alert variant="danger">{error}</Alert>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => window.location.reload()}>
                {common("retry")}
              </button>
            </div>
          ) : subjects ? (
            <ExamSetup
              subjects={subjects}
              onStart={(subject, questionCount, minutes) => {
                setActive({ subject, questionCount, minutes, key: Date.now() });
                setView("player");
              }}
              onHistory={() => setView("history")}
            />
          ) : null}
        </>
      ) : view === "player" && active ? (
        <ExamPlayer
          key={active.key}
          subject={active.subject}
          questionCount={active.questionCount}
          minutes={active.minutes}
          onExit={() => {
            setView("history");
            setActive(null);
          }}
        />
      ) : view === "history" ? (
        <HistoryList subjects={subjects ?? []} onBack={() => setView("setup")} />
      ) : null}
    </ProtectedShell>
  );
}