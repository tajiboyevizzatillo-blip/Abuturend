"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { ReportList } from "@/components/report/report-list";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { createCertificate, type CertificateStyle } from "@/lib/certificates";
import { fetchReport, type SessionReport } from "@/lib/sessions";

export default function ResultsPage() {
  const t = useTranslations("results");
  const exam = useTranslations("exam");
  const common = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params?.id ?? 0);
  const validId = Number.isInteger(id) && id > 0;

  const [report, setReport] = useState<SessionReport | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState(false);
  const [certStyle, setCertStyle] = useState<CertificateStyle | null>(null);
  const [certError, setCertError] = useState<string | null>(null);

  useEffect(() => {
    if (!validId) return;
    let ignore = false;
    fetchReport(id)
      .then((data) => {
        if (!ignore) setReport(data);
      })
      .catch((e) => {
        if (ignore) return;
        if (e instanceof ApiError && (e.status === 404 || e.status === 409)) {
          setMissing(true);
        } else {
          setError(true);
        }
      });
    return () => {
      ignore = true;
    };
  }, [id, validId]);

  const issueCertificate = (style: CertificateStyle) => {
    if (!report || certStyle) return;
    setCertStyle(style);
    setCertError(null);
    createCertificate(report.id, style)
      .then((cert) => router.push(`/verify/${cert.serial}`))
      .catch(() => {
        setCertStyle(null);
        setCertError(common("error"));
      });
  };

  if (error) {
    return (
      <ProtectedShell>
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center gap-4 px-4 py-16 sm:px-6">
          <Alert variant="danger">{common("error")}</Alert>
          <Button variant="secondary" onClick={() => router.back()}>
            {common("back")}
          </Button>
        </div>
      </ProtectedShell>
    );
  }

  if (missing || !validId) {
    return (
      <ProtectedShell>
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center gap-4 px-4 py-16 sm:px-6">
          <Alert variant="danger">{t("notFound")}</Alert>
          <Button variant="secondary" onClick={() => router.back()}>
            {common("back")}
          </Button>
        </div>
      </ProtectedShell>
    );
  }

  if (!report) {
    return (
      <ProtectedShell>
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10 sm:px-6">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-44 rounded-2xl" />
          <Skeleton className="h-24 rounded-2xl" />
          <Skeleton className="h-24 rounded-2xl" />
        </div>
      </ProtectedShell>
    );
  }

  const finishedAt = report.finished_at ?? report.started_at;
  const dateLabel = new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(finishedAt));

  return (
    <ProtectedShell>
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            ← {common("back")}
          </Button>
          <span className="text-xs text-subtle tabular-nums">{dateLabel}</span>
        </div>

        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
          <div className="flex flex-wrap gap-2">
            <span className="badge badge-neutral">
              {report.unified
                ? exam("unifiedTitle")
                : report.mode === "exam"
                  ? exam("title")
                  : exam("practiceTitle")}
            </span>
          </div>
        </div>

        {/* Score summary */}
        <div className="card flex flex-col items-center gap-5 p-6 sm:flex-row sm:justify-around sm:p-8">
          <div
            className="relative h-32 w-32 shrink-0"
            style={{ "--p": report.score_percent } as React.CSSProperties}
            role="progressbar"
            aria-valuenow={report.score_percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t("totalScore")}
          >
            <div className="score-ring absolute inset-0" />
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold tabular-nums">{report.score_percent}%</span>
              <span className="text-xs font-medium text-muted">{t("percentage")}</span>
            </div>
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            <div className="flex items-center gap-2 rounded-xl bg-success-soft px-4 py-2.5">
              <span className="text-sm font-semibold text-success">
                {t("correct")}: {report.correct_answers}
              </span>
            </div>
            <div className="flex items-center gap-2 rounded-xl bg-danger-soft px-4 py-2.5">
              <span className="text-sm font-semibold text-danger">
                {t("incorrect")}: {report.incorrect_answers}
              </span>
            </div>
            <div className="flex items-center gap-2 rounded-xl bg-surface-subtle px-4 py-2.5">
              <span className="text-sm font-semibold text-muted">
                {t("unanswered")}: {report.unanswered}
              </span>
            </div>
          </div>
        </div>

        {/* Certificate CTA — only the unified exam issues certificates */}
        {report.unified ? (
          <div className="card flex flex-col items-center gap-3 p-6 text-center">
            <p className="font-semibold">{exam("certTitle")}</p>
            {certError ? <p className="text-sm text-danger">{certError}</p> : null}
            <div className="flex flex-wrap justify-center gap-3">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => issueCertificate("international")}
                disabled={certStyle !== null}
              >
                {exam("certInternational")}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => issueCertificate("local")}
                disabled={certStyle !== null}
              >
                {exam("certLocal")}
              </button>
            </div>
          </div>
        ) : null}

        <ReportList report={report} />
      </div>
    </ProtectedShell>
  );
}
