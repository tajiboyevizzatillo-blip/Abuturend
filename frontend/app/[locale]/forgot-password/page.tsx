"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link } from "@/i18n/navigation";
import { api, ApiError, extractFieldError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth");
  const common = useTranslations("common");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api("/auth/password-reset/", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      // The endpoint always answers 200 (no account enumeration), so "sent"
      // is shown either way.
      setSent(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? extractFieldError(err.detail) ?? t("errorRequired")
          : t("errorRequired")
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell
      title={t("forgotTitle")}
      footer={
        <>
          {t("haveAccount")}{" "}
          <Link href="/login" className="font-semibold text-primary hover:underline">
            {t("loginLink")}
          </Link>
        </>
      }
    >
      {sent ? (
        <Alert variant="success">{t("forgotSent")}</Alert>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {error ? <Alert variant="danger">{error}</Alert> : null}
          <Input
            label={t("email")}
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" disabled={pending} className="w-full">
            {pending ? common("loading") : t("forgotBtn")}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}