"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchCertificates, type Certificate } from "@/lib/certificates";
import { cn } from "@/lib/utils";

export default function CertificatesPage() {
  const t = useTranslations("cert");
  const [items, setItems] = useState<Certificate[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let ignore = false;
    fetchCertificates()
      .then((data) => {
        if (!ignore) setItems(data);
      })
      .catch(() => {
        if (!ignore) setError(true);
      });
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <ProtectedShell>
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-extrabold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-subtle">{t("subtitle")}</p>
        </div>

        {error ? <Alert variant="danger">{t("loadError")}</Alert> : null}

        {!items && !error ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-24 rounded-2xl" />
            <Skeleton className="h-24 rounded-2xl" />
          </div>
        ) : items && items.length === 0 ? (
          <div className="card flex flex-col items-center gap-4 p-12 text-center">
            <span className="text-5xl">🎓</span>
            <p className="text-lg font-semibold">{t("empty")}</p>
            <p className="max-w-md text-sm text-subtle">{t("emptyHint")}</p>
            <Link href="/mock-exams" className="btn btn-primary">
              {t("goExam")}
            </Link>
          </div>
        ) : items ? (
          <div className="flex flex-col gap-3">
            {items.map((c) => (
              <Link
                key={c.id}
                href={`/verify/${c.serial}`}
                className="card card-hover flex flex-wrap items-center gap-4 p-5"
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-lg">
                  📜
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="font-semibold">
                    {c.style === "international" ? t("international") : t("local")}
                  </span>
                  <span className="text-xs text-subtle">
                    {t("serial")}: <span className="font-mono">{c.serial}</span>
                  </span>
                </span>
                <span
                  className={cn(
                    "badge",
                    c.passed ? "badge-success" : "badge-neutral"
                  )}
                >
                  {c.score_percent}%
                </span>
                <span className="badge badge-primary">{c.grade}</span>
              </Link>
            ))}
          </div>
        ) : null}
      </div>
    </ProtectedShell>
  );
}
