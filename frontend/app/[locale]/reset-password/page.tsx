"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { AuthShell } from "@/components/auth/auth-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError, extractFieldError } from "@/lib/api";

export default function ResetPasswordPage() {
  const t = useTranslations("auth");
  const common = useTranslations("common");
  const router = useRouter();
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid") ?? "";
  const token = searchParams.get("token") ?? "";

  const [form, setForm] = useState({ new_password: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  const linkMissing = !uid || !token;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.new_password !== form.confirm) {
      setError(t("passwordMismatch"));
      return;
    }
    setPending(true);
    setError(null);
    try {
      await api("/auth/password-reset/confirm/", {
        method: "POST",
        body: JSON.stringify({ uid, token, new_password: form.new_password }),
      });
      setDone(true);
      setTimeout(() => router.replace("/login"), 2500);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? extractFieldError(err.detail, "token") ??
            extractFieldError(err.detail, "uid") ??
            extractFieldError(err.detail) ??
            t("resetInvalid")
          : t("resetInvalid")
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell
      title={t("resetTitle")}
      footer={
        <>
          {t("haveAccount")}{" "}
          <Link href="/login" className="font-semibold text-primary hover:underline">
            {t("loginLink")}
          </Link>
        </>
      }
    >
      {done ? (
        <Alert variant="success">{t("resetSuccess")}</Alert>
      ) : linkMissing ? (
        <div className="flex flex-col gap-4">
          <Alert variant="danger">{t("resetInvalid")}</Alert>
          <Link href="/forgot-password" className="btn btn-secondary w-full">
            {t("forgotBtn")}
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {error ? <Alert variant="danger">{error}</Alert> : null}
          <Input
            label={t("newPassword")}
            name="new_password"
            type="password"
            autoComplete="new-password"
            required
            hint={t("passwordHint")}
            value={form.new_password}
            onChange={(e) => setForm({ ...form, new_password: e.target.value })}
          />
          <Input
            label={t("confirmPassword")}
            name="confirm"
            type="password"
            autoComplete="new-password"
            required
            value={form.confirm}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })}
          />
          <Button type="submit" disabled={pending} className="w-full">
            {pending ? common("loading") : t("resetBtn")}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
