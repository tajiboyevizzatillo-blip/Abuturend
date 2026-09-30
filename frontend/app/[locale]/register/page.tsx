"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/components/providers/auth-provider";
import { api, ApiError, extractFieldError, type CurrentUser } from "@/lib/api";
import { fetchOnboardingStatus } from "@/lib/onboarding";
import { Link } from "@/i18n/navigation";

export default function RegisterPage() {
  const t = useTranslations("auth");
  const common = useTranslations("common");
  const { setUser } = useAuth();
  const router = useRouter();

  const [form, setForm] = useState({
    username: "",
    email: "",
    phone: "",
    first_name: "",
    last_name: "",
    password: "",
    confirm: "",
    role: "student",
  });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);

  const set = (key: string, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    setFieldErrors({});

    if (form.password !== form.confirm) {
      setFieldErrors({ confirm: t("errorRequired") });
      setPending(false);
      return;
    }

    try {
      const user = await api<CurrentUser>("/auth/register/", {
        method: "POST",
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          phone: form.phone,
          first_name: form.first_name,
          last_name: form.last_name,
          password: form.password,
          role: form.role,
        }),
      });
      setUser(user);
      // New student accounts go straight to the wizard so the plan exists from
      // day one; teachers have no DTM study plan.
      const onboarding =
        user.role === "student"
          ? await fetchOnboardingStatus()
              .then((s) => s.needs_onboarding)
              .catch(() => false)
          : false;
      router.replace(onboarding ? "/onboarding" : "/dashboard");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && typeof err.detail === "object") {
        const obj = err.detail as Record<string, unknown>;
        const mapped: Record<string, string> = {};
        for (const [k, v] of Object.entries(obj)) {
          if (Array.isArray(v) && v.length) {
            mapped[k] = String(v[0]);
          }
        }
        if (Object.keys(mapped).length) {
          setFieldErrors(mapped);
          // A field error on a control without inline display (role select)
          // would otherwise fail silently — surface it as the form alert too.
          setError(mapped.role ?? mapped.username ?? null);
        } else setError(extractFieldError(err.detail) ?? t("errorRequired"));
      } else {
        setError(t("errorRequired"));
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell
      title={t("registerTitle")}
      footer={
        <>
          {t("haveAccount")}{" "}
          <Link href="/login" className="font-semibold text-primary hover:underline">
            {t("loginLink")}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {error ? <Alert variant="danger">{error}</Alert> : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label={t("firstName")}
            name="first_name"
            autoComplete="given-name"
            value={form.first_name}
            error={fieldErrors.first_name}
            onChange={(e) => set("first_name", e.target.value)}
          />
          <Input
            label={t("lastName")}
            name="last_name"
            autoComplete="family-name"
            value={form.last_name}
            error={fieldErrors.last_name}
            onChange={(e) => set("last_name", e.target.value)}
          />
        </div>
        <Input
          label={t("username")}
          name="username"
          autoComplete="username"
          required
          value={form.username}
          error={fieldErrors.username}
          onChange={(e) => set("username", e.target.value)}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label={`${t("email")} (${common("optional")})`}
            name="email"
            type="email"
            autoComplete="email"
            value={form.email}
            error={fieldErrors.email}
            onChange={(e) => set("email", e.target.value)}
          />
          <Input
            label={`${t("phone")} (${common("optional")})`}
            name="phone"
            type="tel"
            autoComplete="tel"
            value={form.phone}
            error={fieldErrors.phone}
            onChange={(e) => set("phone", e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="label">{t("role")}</label>
          <select
            className="input"
            value={form.role}
            onChange={(e) => set("role", e.target.value)}
          >
            <option value="student">{t("roleStudent")}</option>
            <option value="teacher">{t("roleTeacher")}</option>
          </select>
          {fieldErrors.role ? (
            <span className="text-xs font-medium text-danger">{fieldErrors.role}</span>
          ) : null}
        </div>
        <Input
          label={t("password")}
          name="password"
          type="password"
          autoComplete="new-password"
          required
          hint={t("passwordHint")}
          value={form.password}
          error={fieldErrors.password}
          onChange={(e) => set("password", e.target.value)}
        />
        <Input
          label={t("confirmPassword")}
          name="confirm"
          type="password"
          autoComplete="new-password"
          required
          value={form.confirm}
          error={fieldErrors.confirm}
          onChange={(e) => set("confirm", e.target.value)}
        />
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? common("loading") : t("registerBtn")}
        </Button>
      </form>
    </AuthShell>
  );
}