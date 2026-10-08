"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/components/providers/auth-provider";
import { api, ApiError, extractFieldError, type CurrentUser } from "@/lib/api";
import { fetchOnboardingStatus } from "@/lib/onboarding";
import { Link } from "@/i18n/navigation";
import { safeNext } from "@/lib/navigation";

export default function LoginPage() {
  const t = useTranslations("auth");
  const common = useTranslations("common");
  const { setUser } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  // Only same-site paths: an attacker-supplied next=https://evil.com must not
  // turn the login button into an open redirect. The previous guard rejected
  // "//" but not "/\evil.com" — browsers normalise "\" to "/", so that value
  // resolves protocol-relative to an attacker's host.
  const rawNext = searchParams.get("next") || "";
  const next = safeNext(rawNext);

  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const user = await api<CurrentUser>("/auth/login/", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setUser(user);
      // A student who never finished the wizard lands there first; the auth
      // gate would redirect anyway, so do it explicitly to avoid a flash of
      // the requested page. The `next` target is intentionally dropped here.
      const onboarding =
        user.role === "student"
          ? await fetchOnboardingStatus()
              .then((s) => s.needs_onboarding)
              .catch(() => false)
          : false;
      router.replace(onboarding ? "/onboarding" : next);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? extractFieldError(err.detail) ?? t("errorInvalid")
          : t("errorInvalid")
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell
      title={t("loginTitle")}
      subtitle={t("welcomeBack")}
      footer={
        <>
          {t("noAccount")}{" "}
          <Link href="/register" className="font-semibold text-primary hover:underline">
            {t("registerLink")}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {error ? <Alert variant="danger">{error}</Alert> : null}
        <Input
          label={t("username")}
          name="username"
          autoComplete="username"
          required
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
        />
        <Input
          label={t("password")}
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <div className="flex justify-end">
          <Link href="/forgot-password" className="text-sm font-semibold text-primary hover:underline">
            {t("forgotPassword")}
          </Link>
        </div>
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? common("loading") : t("loginBtn")}
        </Button>
      </form>
    </AuthShell>
  );
}