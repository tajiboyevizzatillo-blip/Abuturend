"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Link } from "@/i18n/navigation";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/components/providers/auth-provider";
import { api, ApiError, extractFieldError, type CurrentUser } from "@/lib/api";

// Keyed by user id: the form state is rebuilt whenever the account changes,
// so an empty form can never PATCH blank values over a loaded profile.
function DetailsCard({ user, onSaved }: { user: CurrentUser; onSaved: () => Promise<void> }) {
  const t = useTranslations("auth");
  const common = useTranslations("common");

  const [form, setForm] = useState({
    first_name: user.first_name ?? "",
    last_name: user.last_name ?? "",
    email: user.email ?? "",
    phone: user.phone ?? "",
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true);
    setSaved(false);
    setError(null);
    try {
      await api("/auth/me/", {
        method: "PATCH",
        body: JSON.stringify(form),
      });
      await onSaved();
      setSaved(true);
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
    <Card>
      <CardHeader>
        <CardTitle>{t("profile")}</CardTitle>
        <CardDescription>{t("personalInfo")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={saveProfile} className="flex flex-col gap-4">
          {saved ? <Alert variant="success">{t("profileSaved")}</Alert> : null}
          {error ? <Alert variant="danger">{error}</Alert> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label={t("firstName")}
              name="first_name"
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            />
            <Input
              label={t("lastName")}
              name="last_name"
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            />
          </div>
          <Input
            label={t("email")}
            name="email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <Input
            label={t("phone")}
            name="phone"
            type="tel"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
          <div className="flex justify-end">
            <Button type="submit" disabled={pending}>
              {pending ? common("loading") : common("save")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export default function ProfilePage() {
  const t = useTranslations("auth");
  const common = useTranslations("common");
  const certT = useTranslations("cert");
  const onbT = useTranslations("onboarding");
  const { user, refresh } = useAuth();

  const [passSaved, setPassSaved] = useState(false);
  const [passError, setPassError] = useState<string | null>(null);
  const [passPending, setPassPending] = useState(false);

  const [pass, setPass] = useState({
    old_password: "",
    new_password: "",
    confirm: "",
  });

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPassPending(true);
    setPassError(null);
    setPassSaved(false);
    if (pass.new_password !== pass.confirm) {
      setPassError(t("passwordMismatch"));
      setPassPending(false);
      return;
    }
    try {
      await api("/auth/change-password/", {
        method: "POST",
        body: JSON.stringify({
          old_password: pass.old_password,
          new_password: pass.new_password,
        }),
      });
      setPass({ old_password: "", new_password: "", confirm: "" });
      setPassSaved(true);
    } catch (err) {
      setPassError(
        err instanceof ApiError
          ? (extractFieldError(err.detail, "old_password") ??
              extractFieldError(err.detail) ??
              t("errorRequired"))
          : t("errorRequired")
      );
    } finally {
      setPassPending(false);
    }
  };

  return (
    <ProtectedShell>
      <div className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6">
        <div className="bg-navy relative overflow-hidden rounded-3xl p-6 text-white sm:p-8">
          <div aria-hidden className="pointer-events-none absolute -right-14 -top-14 h-48 w-48 rounded-full bg-primary/40 blur-3xl" />
          <div aria-hidden className="pointer-events-none absolute -bottom-16 -left-8 h-40 w-40 rounded-full bg-teal/30 blur-3xl" />
          <div className="relative flex flex-wrap items-center gap-4">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/15 text-2xl font-extrabold text-white ring-1 ring-white/20 backdrop-blur-md">
              {(user?.first_name?.[0] || user?.username?.[0] || "A").toUpperCase()}
            </span>
            <div className="flex flex-col gap-1">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-300">
                {t("profile")}
              </p>
              <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
                {user?.first_name || user?.username}
              </h1>
              <span className="mt-1 inline-flex w-fit items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold text-white backdrop-blur-md">
                Abituriyent · {user?.username}
              </span>
            </div>
          </div>
        </div>
        <div className="mt-6 flex flex-col gap-6">
          {user ? (
            <DetailsCard key={user.id} user={user} onSaved={refresh} />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{t("profile")}</CardTitle>
                <CardDescription>{t("personalInfo")}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted">{common("loading")}</p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{t("changePasswordTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={changePassword} className="flex flex-col gap-4">
                {passSaved ? <Alert variant="success">{t("passwordChanged")}</Alert> : null}
                {passError ? <Alert variant="danger">{passError}</Alert> : null}
                <Input
                  label={t("oldPassword")}
                  name="old_password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={pass.old_password}
                  onChange={(e) => setPass({ ...pass, old_password: e.target.value })}
                />
                <Input
                  label={t("newPassword")}
                  name="new_password"
                  type="password"
                  autoComplete="new-password"
                  required
                  hint={t("passwordHint")}
                  value={pass.new_password}
                  onChange={(e) => setPass({ ...pass, new_password: e.target.value })}
                />
                <Input
                  label={t("confirmPassword")}
                  name="confirm"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={pass.confirm}
                  onChange={(e) => setPass({ ...pass, confirm: e.target.value })}
                />
                <div className="flex justify-end">
                  <Button type="submit" disabled={passPending} variant="secondary">
                    {passPending ? common("loading") : common("save")}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{onbT("planSettingsTitle")}</CardTitle>
              <CardDescription>{onbT("planSettingsHint")}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-3">
              <Link href="/onboarding" className="btn btn-secondary">
                {onbT("rebuild")}
              </Link>
              <Link href="/dashboard" className="text-sm font-semibold text-primary hover:underline">
                {onbT("todayTitle")}
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{certT("title")}</CardTitle>
              <CardDescription>{certT("subtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Link href="/certificates" className="btn btn-secondary">
                📜 {certT("myCerts")}
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </ProtectedShell>
  );
}
