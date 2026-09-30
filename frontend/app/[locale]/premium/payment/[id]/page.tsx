"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import {
  fetchPayment,
  type Payment,
  type PaymentStatus,
} from "@/lib/payments";

const POLL_MS = 3000;

export default function PaymentStatusPage() {
  const t = useTranslations("premium");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams();
  const rawId = params.id;
  const paymentId = Array.isArray(rawId) ? rawId[0] : (rawId ?? "");

  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const refresh = useCallback((): Promise<Payment | null> => {
    return fetchPayment(paymentId)
      .then((next) => {
        setPayment(next);
        setError(null);
        return next;
      })
      .catch((e) => {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          setError(t("needLogin"));
        } else if (e instanceof ApiError && e.status === 404) {
          setError(t("payNotFound"));
        } else {
          setError(t("error"));
        }
        return null;
      });
  }, [paymentId, t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while the payment is still pending.
  useEffect(() => {
    if (!payment || payment.status !== "pending") return;
    const timer = setTimeout(refresh, POLL_MS);
    return () => clearTimeout(timer);
  }, [payment, refresh]);

  // Paid -> back to the premium page shortly.
  useEffect(() => {
    if (payment?.status !== "paid") return;
    const redirect = setTimeout(
      () => router.replace(`/${locale}/premium`),
      4000
    );
    return () => clearTimeout(redirect);
  }, [payment, locale, router]);

  const reopen = () => {
    if (payment?.payment_url) {
      window.open(payment.payment_url, "_blank", "noopener");
    }
  };

  const checkNow = () => {
    setChecking(true);
    refresh().then(() => setChecking(false));
  };

  const status: PaymentStatus | null = payment?.status ?? null;

  return (
    <ProtectedShell>
      <div className="mx-auto w-full max-w-xl flex-1 px-4 py-10 sm:px-6">
        <div className="card flex flex-col items-center gap-4 p-8 text-center">
          <span className="badge badge-primary w-fit">{t("payTitle")}</span>

          {!payment && !error ? (
            <div className="flex w-full flex-col gap-3">
              <Skeleton className="h-20" />
              <Skeleton className="h-10" />
            </div>
          ) : null}

          {error ? <Alert variant="danger">{error}</Alert> : null}

          {status === "pending" ? (
            <>
              <div className="flex items-center gap-2 text-sm text-muted">
                <span
                  aria-hidden
                  className="h-2.5 w-2.5 animate-pulse rounded-full bg-warning"
                />
                {t("payPending")}
              </div>
              <p className="text-xs text-muted">{t("payPendingHint")}</p>
              <div className="flex w-full flex-col gap-2 sm:flex-row">
                <Button
                  className="flex-1"
                  variant="secondary"
                  disabled={!payment?.payment_url}
                  onClick={reopen}
                >
                  {t("payOpen")}
                </Button>
                <Button
                  className="flex-1"
                  variant="primary"
                  disabled={checking}
                  onClick={checkNow}
                >
                  {checking ? t("payChecking") : t("payCheck")}
                </Button>
              </div>
            </>
          ) : null}

          {status === "paid" ? (
            <Alert variant="success">{t("payPaid")}</Alert>
          ) : null}

          {status === "cancelled" ? (
            <Alert variant="danger">{t("payCancelled")}</Alert>
          ) : null}

          {status === "failed" ? (
            <Alert variant="danger">{t("payFailed")}</Alert>
          ) : null}

          {status && status !== "pending" ? (
            <Button
              className="w-full"
              variant="primary"
              onClick={() => router.push(`/${locale}/premium`)}
            >
              {t("payBack")}
            </Button>
          ) : null}
        </div>
      </div>
    </ProtectedShell>
  );
}
