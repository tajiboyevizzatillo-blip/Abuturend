"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/providers/auth-provider";
import { ApiError } from "@/lib/api";
import { localizedName } from "@/lib/catalog";
import {
  fetchPlans,
  fetchSubscription,
  subscribe,
  type SubscriptionPlan,
  type SubscriptionState,
} from "@/lib/premium";
import { startCheckout, type PaymentProvider } from "@/lib/payments";
import { cn } from "@/lib/utils";

function planFeatureKeys(t: ReturnType<typeof useTranslations>, tier: string) {
  return tier === "pro"
    ? [t("featuresPro1"), t("featuresPro2"), t("featuresPro3")]
    : [t("featuresFree1")];
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat("uz-UZ").format(price);
}

export default function PremiumPage() {
  const t = useTranslations("premium");
  const locale = useLocale();
  const router = useRouter();
  const { user } = useAuth();

  const [plans, setPlans] = useState<SubscriptionPlan[] | null>(null);
  const [sub, setSub] = useState<SubscriptionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingCode, setPendingCode] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    fetchPlans()
      .then(setPlans)
      .catch(() => setError(t("error")));
    if (user) {
      fetchSubscription()
        .then(setSub)
        .catch(() => setSub(null));
    }
  }, [t, user]);

  const onSubscribe = async (
    plan: SubscriptionPlan,
    provider?: PaymentProvider
  ) => {
    setPendingCode(plan.code);
    setNotice(null);
    setError(null);
    try {
      if (plan.price_uzs > 0) {
        const payment = await startCheckout(
          plan.code,
          provider ?? "payme",
          `/${locale}/premium/payment/{id}/`
        );
        if (payment.payment_url) {
          window.open(payment.payment_url, "_blank", "noopener");
        }
        router.push(`/${locale}/premium/payment/${payment.id}`);
        return;
      }
      const next = await subscribe(plan.code);
      setSub(next);
      setNotice(t("subscribed"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        setError(t("paywall"));
      } else if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        setError(t("needLogin"));
      } else {
        setError(t("error"));
      }
    } finally {
      setPendingCode(null);
    }
  };

  const activePlan = sub?.plan ?? null;

  return (
    <ProtectedShell>
      <div className="mx-auto w-full max-w-4xl flex-1 px-4 py-8 sm:px-6">
        <div className="bg-navy relative overflow-hidden rounded-3xl p-6 text-white sm:p-8">
          <div aria-hidden className="pointer-events-none absolute -right-14 -top-14 h-48 w-48 rounded-full bg-primary/40 blur-3xl" />
          <div aria-hidden className="pointer-events-none absolute -bottom-16 -left-8 h-40 w-40 rounded-full bg-teal/30 blur-3xl" />
          <div className="relative flex flex-col gap-2">
            <span className="badge badge-warning w-fit">PRO</span>
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
              {t("title")}
            </h1>
            <p className="max-w-xl text-sm text-slate-300">{t("subtitle")}</p>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-2xl bg-white/10 px-4 py-2 text-sm font-semibold ring-1 ring-white/15 backdrop-blur-md">
                {t("currentStatus")}:{" "}
                {activePlan
                  ? localizedName(
                      {
                        name_uz: activePlan.plan_name_uz,
                        name_ru: activePlan.plan_name_ru,
                        name_en: activePlan.plan_name_en,
                      },
                      locale
                    )
                  : t("noPlan")}
                {activePlan ? (
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-bold uppercase",
                      activePlan.is_active ? "bg-teal/80" : "bg-white/20"
                    )}
                  >
                    {activePlan.is_active ? t("active") : t("expired")}
                  </span>
                ) : null}
              </span>
              <span className="inline-flex items-center gap-2 rounded-2xl bg-white/10 px-4 py-2 text-sm font-semibold ring-1 ring-white/15 backdrop-blur-md">
                {t("remainingToday")}:{" "}
                {sub?.remaining_sessions_today === null
                  ? t("unlimited")
                  : (sub?.remaining_sessions_today ?? 0)}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-4">
          {error ? <Alert variant="danger">{error}</Alert> : null}
          {notice ? <Alert variant="success">{notice}</Alert> : null}

          {!plans && !error ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {[0, 1].map((i) => (
                <Skeleton key={i} className="h-72" />
              ))}
            </div>
          ) : plans ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {plans.map((plan) => {
                const isProPlan = plan.tier === "pro";
                const isActivePlan =
                  activePlan?.plan === plan.code && (sub?.is_premium ?? false);
                return (
                  <div
                    key={plan.code}
                    className={cn(
                      "card flex flex-col gap-4 p-6",
                      isProPlan && "border-primary/40 ring-1 ring-primary/25"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex flex-col gap-1">
                        <span
                          className={cn(
                            "badge w-fit",
                            isProPlan ? "badge-primary" : "badge-neutral"
                          )}
                        >
                          {isProPlan ? t("proBadge") : t("freeBadge")}
                        </span>
                        <h2 className="text-lg font-extrabold tracking-tight">
                          {localizedName(plan, locale)}
                        </h2>
                      </div>
                      {isProPlan ? (
                        <span className="badge badge-warning">{t("mostPopular")}</span>
                      ) : null}
                    </div>

                    <p className="text-sm text-muted">
                      {localizedName(
                        {
                          name_uz: plan.description_uz,
                          name_ru: plan.description_ru,
                          name_en: plan.description_en,
                        },
                        locale
                      )}
                    </p>

                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-extrabold tracking-tight">
                        {plan.price_uzs === 0
                          ? t("free")
                          : `${formatPrice(plan.price_uzs)}`}
                      </span>
                      <span className="text-sm text-muted">
                        {plan.price_uzs === 0 ? "" : t("price")}
                      </span>
                    </div>

                    <ul className="flex flex-col gap-2 text-sm">
                      <li className="flex items-center gap-2">
                        <span className="text-success">✓</span>
                        <span className="text-muted">
                          {plan.unlimited_sessions
                            ? t("unlimited")
                            : t("perDay", { count: plan.max_sessions_per_day ?? 0 })}
                        </span>
                      </li>
                      {planFeatureKeys(t, plan.tier).map((f) => (
                        <li key={f} className="flex items-center gap-2">
                          <span className="text-success">✓</span>
                          <span className="text-muted">{f}</span>
                        </li>
                      ))}
                      <li className="flex items-center gap-2">
                        <span className="text-success">✓</span>
                        <span className="text-muted">
                          {t("duration")}: {plan.duration_days}{" "}
                          {locale === "en" ? "days" : locale === "ru" ? "дней" : "kun"}
                        </span>
                      </li>
                    </ul>

                    <div className="mt-auto space-y-2 pt-2">
                      {isProPlan ? (
                        <>
                          <p className="text-center text-xs text-muted">
                            {t("chooseProvider")}
                          </p>
                          <div className="grid grid-cols-2 gap-2">
                            <Button
                              variant="primary"
                              disabled={
                                !user || isActivePlan || pendingCode !== null
                              }
                              onClick={() => onSubscribe(plan, "payme")}
                            >
                              {!user
                                ? t("needLogin")
                                : isActivePlan
                                  ? t("active")
                                  : pendingCode === plan.code
                                    ? t("subscribing")
                                    : "Payme"}
                            </Button>
                            <Button
                              variant="primary"
                              disabled={
                                !user || isActivePlan || pendingCode !== null
                              }
                              onClick={() => onSubscribe(plan, "click")}
                            >
                              {!user
                                ? t("needLogin")
                                : isActivePlan
                                  ? t("active")
                                  : pendingCode === plan.code
                                    ? t("subscribing")
                                    : "Click"}
                            </Button>
                          </div>
                        </>
                      ) : (
                        <Button
                          className="w-full"
                          variant="secondary"
                          disabled={
                            !user || isActivePlan || pendingCode !== null
                          }
                          onClick={() => onSubscribe(plan)}
                        >
                          {!user
                            ? t("needLogin")
                            : isActivePlan
                              ? t("active")
                              : pendingCode === plan.code
                                ? t("subscribing")
                                : t("subscribe")}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}

          {plans && !user ? (
            <p className="text-center text-sm text-muted">{t("needLogin")}</p>
          ) : null}
        </div>
      </div>
    </ProtectedShell>
  );
}
