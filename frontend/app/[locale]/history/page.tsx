"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchSessionList, type SessionListItem, type SessionMode } from "@/lib/sessions";
import { cn } from "@/lib/utils";

type ModeFilter = "all" | SessionMode;

function localName(
  o: { name_uz?: string; name_ru?: string; name_en?: string } | null,
  locale: string
): string {
  if (!o) return "";
  if (locale === "ru") return o.name_ru || o.name_uz || "";
  if (locale === "en") return o.name_en || o.name_uz || "";
  return o.name_uz || "";
}

function csvCell(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  // Quote when needed so commas/quotes in names survive.
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function exportCsv(rows: SessionListItem[], locale: string) {
  const header = [
    "id",
    "mode",
    "subject",
    "status",
    "question_count",
    "correct",
    "incorrect",
    "score_percent",
    "started_at",
    "finished_at",
  ];
  const lines = rows.map((r) =>
    [
      r.id,
      r.mode,
      r.subject ? localName(r.subject, locale) : "unified",
      r.status,
      r.question_count,
      r.correct_answers ?? "",
      r.incorrect_answers ?? "",
      r.score_percent ?? "",
      r.started_at,
      r.finished_at ?? "",
    ]
      .map(csvCell)
      .join(",")
  );
  // BOM so Excel opens UTF-8 (Cyrillic/Uzbek letters) correctly.
  const blob = new Blob(["\uFEFF" + [header.join(","), ...lines].join("\r\n")], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "abituriyent-natijalar.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export default function HistoryPage() {
  const t = useTranslations("history");
  const common = useTranslations("common");
  const exam = useTranslations("exam");
  const locale = useLocale();
  const [rows, setRows] = useState<SessionListItem[] | null>(null);
  const [error, setError] = useState(false);
  const [mode, setMode] = useState<ModeFilter>("all");
  const [subjectId, setSubjectId] = useState<number | null | "all">("all");

  useEffect(() => {
    let ignore = false;
    fetchSessionList()
      .then((data) => {
        if (!ignore) setRows(data);
      })
      .catch(() => {
        if (!ignore) setError(true);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const subjects = useMemo(() => {
    const map = new Map<number, string>();
    for (const r of rows ?? []) {
      if (r.subject) map.set(r.subject.id, localName(r.subject, locale));
    }
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [rows, locale]);

  const filtered = useMemo(
    () =>
      (rows ?? []).filter(
        (r) =>
          (mode === "all" || r.mode === mode) &&
          (subjectId === "all" ||
            (subjectId === null ? r.subject === null : r.subject?.id === subjectId))
      ),
    [rows, mode, subjectId]
  );

  return (
    <ProtectedShell>
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
            <p className="text-sm text-subtle">{t("subtitle")}</p>
          </div>
          {rows && rows.length ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => exportCsv(filtered, locale)}
              disabled={filtered.length === 0}
            >
              ↓ {t("exportCsv")}
            </Button>
          ) : null}
        </div>

        {error ? <Alert variant="danger">{common("error")}</Alert> : null}

        {/* Filters */}
        {rows && rows.length ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex flex-wrap gap-2" role="group" aria-label={t("title")}>
              {(["all", "exam", "practice"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  aria-pressed={mode === m}
                  className={cn("btn btn-sm", mode === m ? "btn-primary" : "btn-secondary")}
                >
                  {m === "all"
                    ? t("filterAll")
                    : m === "exam"
                      ? exam("title")
                      : exam("practiceTitle")}
                </button>
              ))}
            </div>
            <select
              className="input sm:max-w-[16rem]"
              value={subjectId === null ? "unified" : String(subjectId)}
              onChange={(e) => {
                const v = e.target.value;
                if (v === "all") setSubjectId("all");
                else if (v === "unified") setSubjectId(null);
                else setSubjectId(Number(v));
              }}
              aria-label={t("subjectAll")}
            >
              <option value="all">{t("subjectAll")}</option>
              <option value="unified">{exam("unifiedTitle")}</option>
              {subjects.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
            <span className="text-xs text-subtle tabular-nums sm:ml-auto">
              {t("count", { count: filtered.length })}
            </span>
          </div>
        ) : null}

        {!rows && !error ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
        ) : rows && filtered.length === 0 ? (
          <div className="card flex flex-col items-center gap-4 p-12 text-center">
            <p className="text-lg font-semibold">{t("empty")}</p>
            <p className="max-w-md text-sm text-subtle">{t("emptyHint")}</p>
            <Link href="/mock-exams" className="btn btn-primary">
              {t("goExam")}
            </Link>
          </div>
        ) : filtered.length ? (
          <div className="flex flex-col gap-3">
            {filtered.map((r) => {
              const name = r.subject
                ? localName(r.subject, locale)
                : exam("unifiedTitle");
              const done = r.status === "finished";
              const inner = (
                <>
                  <div
                    className={cn(
                      "relative h-14 w-14 shrink-0",
                      done && (r.score_percent ?? 0) >= 60 ? "text-success" : "text-danger"
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
                    <div className="absolute inset-0 flex items-center justify-center text-xs font-bold tabular-nums">
                      {done ? `${r.score_percent ?? 0}%` : "…"}
                    </div>
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <p className="truncate font-semibold">{name}</p>
                    <p className="text-xs text-subtle">
                      {new Intl.DateTimeFormat(locale, {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      }).format(new Date(r.started_at))}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-2">
                      <span className="badge badge-neutral">
                        {r.mode === "exam" ? exam("title") : exam("practiceTitle")}
                      </span>
                      <span className="badge badge-neutral">
                        {r.correct_answers ?? "…"}/{r.question_count}
                      </span>
                    </div>
                  </div>
                  <span
                    className={cn("badge", done ? "badge-success" : "badge-warning")}
                  >
                    {done ? common("verified") : common("inProgress")}
                  </span>
                </>
              );
              const rowClass = "card card-hover flex items-center gap-4 p-4 sm:p-5";
              return done ? (
                <Link key={r.id} href={`/results/${r.id}`} className={rowClass}>
                  {inner}
                </Link>
              ) : (
                <div key={r.id} className={rowClass}>
                  {inner}
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </ProtectedShell>
  );
}
