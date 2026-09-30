"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchCertificate, type Certificate } from "@/lib/certificates";
import { cn } from "@/lib/utils";

export default function VerifyCertificatePage() {
  const t = useTranslations("cert");
  const params = useParams<{ serial: string }>();
  const serial = params?.serial ?? "";

  const [cert, setCert] = useState<Certificate | null>(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let ignore = false;
    fetchCertificate(serial)
      .then((data) => {
        if (!ignore) setCert(data);
      })
      .catch(() => {
        if (!ignore) setMissing(true);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [serial]);

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 px-4 py-12 sm:px-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-72 rounded-3xl" />
      </div>
    );
  }

  if (missing || !cert) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center gap-5 px-4 py-16 sm:px-6">
        <Alert variant="danger">{t("notFound")}</Alert>
        <p className="text-sm text-subtle">{t("notFoundHint")}</p>
        <Link href="/" className="btn btn-secondary">
          {t("back")}
        </Link>
      </div>
    );
  }

  const intl = cert.style === "international";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href="/" className="btn btn-secondary btn-sm">
          {t("back")}
        </Link>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => window.print()}>
          {t("print")}
        </button>
      </div>

      <div className="card relative overflow-hidden p-8 sm:p-10">
        <div aria-hidden className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex flex-col gap-6">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-widest text-primary">
                Abituriyent
              </span>
              <h1 className="text-xl font-extrabold tracking-tight">
                {intl ? t("international") : t("local")}
              </h1>
            </div>
            <span
              className={cn(
                "badge",
                cert.passed ? "badge-success" : "badge-neutral"
              )}
            >
              ✓ {t("verifyOk")}
            </span>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase tracking-widest text-subtle">
              {t("fullName")}
            </span>
            <span className="text-2xl font-extrabold tracking-tight sm:text-3xl">
              {cert.full_name}
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="flex flex-col gap-1 rounded-2xl bg-surface-subtle p-4">
              <span className="text-xs font-semibold text-subtle">{t("score")}</span>
              <span className="text-2xl font-extrabold tabular-nums">
                {cert.score_percent}%
              </span>
              <span className="text-xs text-muted">
                {cert.correct_answers}/{cert.question_count}
              </span>
            </div>
            <div className="flex flex-col gap-1 rounded-2xl bg-surface-subtle p-4">
              <span className="text-xs font-semibold text-subtle">{t("grade")}</span>
              <span className="text-2xl font-extrabold">{cert.grade}</span>
            </div>
            <div className="flex flex-col gap-1 rounded-2xl bg-surface-subtle p-4">
              <span className="text-xs font-semibold text-subtle">{t("result")}</span>
              <span
                className={cn(
                  "text-lg font-extrabold",
                  cert.passed ? "text-success" : "text-danger"
                )}
              >
                {cert.passed ? t("passed") : t("notPassed")}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap justify-between gap-3 border-t border-border pt-4 text-xs text-subtle">
            <span>
              {t("serial")}: <span className="font-mono font-semibold">{cert.serial}</span>
            </span>
            <span>
              {t("issued")}:{" "}
              {new Date(cert.issued_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>

      <p className="text-center text-xs text-subtle print:hidden">
        {t("verifyUrlHint")}: <span className="font-mono">/verify/{cert.serial}</span>
      </p>
    </div>
  );
}
