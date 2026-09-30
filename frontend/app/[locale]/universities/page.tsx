"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ProtectedShell } from "@/components/layout/protected-shell";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchSubjects, localizedName, type Subject } from "@/lib/catalog";
import {
  fetchUniversities,
  fetchUniversity,
  fetchDirections,
  localizedUniversityName,
  localizedCity,
  localizedDirectionName,
  localizedSubjectName,
  type University,
  type Direction,
} from "@/lib/universities";
import { cn } from "@/lib/utils";

function ArrowIcon({ open = false }: { open?: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={cn(
        "transition-transform duration-200",
        open && "rotate-90"
      )}
    >
      <path d="M5 12h14m-6-6 6 6-6 6" />
    </svg>
  );
}

export default function UniversitiesPage() {
  const t = useTranslations("universities");
  const common = useTranslations("common");
  const locale = useLocale();

  const [universities, setUniversities] = useState<University[] | null>(null);
  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [activeSubject, setActiveSubject] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [directionsBySubject, setDirectionsBySubject] = useState<Map<number, Direction[]>>(new Map());
  const [detail, setDetail] = useState<Map<string, University>>(new Map());
  const [detailFailed, setDetailFailed] = useState<Set<string>>(new Set());

  const reload = () => {
    Promise.all([
      fetchUniversities().then(setUniversities),
      fetchSubjects().then(setSubjects),
    ]).catch(() => setError(common("error")));
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeSubject == null) return;
    let ignore = false;
    fetchDirections({ subject: activeSubject })
      .then((rows) => {
        if (!ignore) setDirectionsBySubject((prev) => new Map(prev).set(activeSubject, rows));
      })
      .catch(() => {
        if (!ignore) setDirectionsBySubject((prev) => new Map(prev).set(activeSubject, []));
      });
    return () => {
      ignore = true;
    };
  }, [activeSubject]);

  const toggle = (slug: string) => {
    if (expanded === slug) {
      setExpanded(null);
      return;
    }
    setExpanded(slug);
    if (!detail.has(slug)) {
      loadDetail(slug);
    }
  };

  const loadDetail = (slug: string) => {
    setDetailFailed((prev) => {
      const next = new Set(prev);
      next.delete(slug);
      return next;
    });
    fetchUniversity(slug)
      .then((u) => setDetail((prev) => new Map(prev).set(slug, u)))
      .catch(() =>
        setDetailFailed((prev) => new Set(prev).add(slug))
      );
  };

  const matches = useMemo(() => {
    if (activeSubject == null) return null;
    return directionsBySubject.get(activeSubject) ?? null;
  }, [activeSubject, directionsBySubject]);

  const visible = useMemo(() => {
    if (!universities) return [];
    const q = query.trim().toLowerCase();
    const docs = matches ?? undefined;
    return universities.filter((u) => {
      const name = localizedUniversityName(u, locale).toLowerCase();
      const city = localizedCity(u, locale).toLowerCase();
      if (q && !name.includes(q) && !city.includes(q)) return false;
      if (docs) {
        const hasMatch = docs.some((d) => d.university.slug === u.slug);
        if (!hasMatch) return false;
      }
      return true;
    });
  }, [universities, query, locale, matches]);

  const directionsFor = (slug: string): Direction[] | null => {
    if (activeSubject != null) {
      return (directionsBySubject.get(activeSubject) ?? []).filter((d) => d.university.slug === slug);
    }
    const u = detail.get(slug);
    return u?.directions ?? null;
  };

  return (
    <ProtectedShell>
      <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-1.5">
            <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{t("title")}</h1>
            <p className="font-serif text-lg italic text-muted">{t("subtitle")}</p>
          </div>
          {universities ? (
            <span className="badge badge-neutral self-start px-3 py-1.5">
              {universities.length}
            </span>
          ) : null}
        </div>

        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative max-w-md flex-1">
            <svg
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-subtle"
              width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input
              className="input pl-10"
              placeholder={t("search")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={t("search")}
            />
          </div>
          {subjects ? (
            <div className="nice-scroll flex gap-2 overflow-x-auto pb-1">
              <button
                type="button"
                onClick={() => setActiveSubject(null)}
                className={cn(
                  "segment-option whitespace-nowrap",
                  activeSubject == null && "segment-option-active"
                )}
              >
                {t("allSubjects")}
              </button>
              {subjects.slice(0, 12).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setActiveSubject(activeSubject === s.id ? null : s.id)}
                  className={cn(
                    "segment-option whitespace-nowrap",
                    activeSubject === s.id && "segment-option-active"
                  )}
                >
                  {localizedName(s, locale)}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="flex flex-col gap-3">
            <Alert variant="danger">{error}</Alert>
            <button type="button" className="btn btn-secondary btn-sm self-start" onClick={() => { setError(null); reload(); }}>
              {common("retry")}
            </button>
          </div>
        ) : null}

        {!universities && !error ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-52" />
            ))}
          </div>
        ) : !error && visible.length === 0 ? (
          <div className="card flex flex-col items-center gap-3 p-14 text-center">
            <p className="text-muted">{common("empty")}</p>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setQuery(""); setActiveSubject(null); }}>
              {common("reset")}
            </button>
          </div>
        ) : !error ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((u) => {
              const isOpen = expanded === u.slug;
              const directions = directionsFor(u.slug);
              return (
                <div key={u.id} className={cn("card card-hover flex flex-col p-6", isOpen && "border-primary/50")}>
                  <div className="flex items-start gap-4">
                    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-navy text-sm font-bold text-primary-foreground shadow-raised">
                      {(u.code || localizedUniversityName(u, locale).charAt(0)).toUpperCase()}
                    </span>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold leading-snug">{localizedUniversityName(u, locale)}</h3>
                      <p className="mt-1 text-sm text-muted">
                        {localizedCity(u, locale)}
                        {u.established ? <> · {u.established}</> : null}
                      </p>
                    </div>
                    <span className="badge badge-primary shrink-0">{u.direction_count}</span>
                  </div>

                  {isOpen ? (
                    <div className="mt-4 flex flex-col gap-3">
                      {activeSubject == null && !directions && !detailFailed.has(u.slug) ? (
                        <Skeleton className="h-24" />
                      ) : activeSubject == null && detailFailed.has(u.slug) ? (
                        <div className="flex items-center justify-between gap-3 rounded-xl bg-danger-soft p-3.5">
                          <span className="text-sm text-danger">{common("error")}</span>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm shrink-0"
                            onClick={() => loadDetail(u.slug)}
                          >
                            {common("retry")}
                          </button>
                        </div>
                      ) : directions && directions.length > 0 ? (
                        directions.map((d) => (
                          <div key={d.id} className="rounded-xl bg-surface-subtle p-3.5">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm font-semibold">{localizedDirectionName(d, locale)}</p>
                              {d.duration_years ? (
                                <span className="badge badge-neutral">{d.duration_years} {t("years")}</span>
                              ) : null}
                            </div>
                            {d.subjects.length > 0 ? (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {d.subjects.map((s) => (
                                  <span key={s.id} className="badge badge-neutral px-2 py-0.5 text-xs">
                                    {localizedSubjectName(s, locale)}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ))
                      ) : (
                        <p className="py-2 text-center text-sm text-subtle">{common("empty")}</p>
                      )}
                      {u.website ? (
                        <a
                          href={u.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {t("officialLink")} ↗
                        </a>
                      ) : null}
                    </div>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => toggle(u.slug)}
                    className="btn btn-ghost btn-sm mt-4 self-start"
                  >
                    {isOpen ? common("cancel") : t("directions")}
                    <ArrowIcon open={isOpen} />
                  </button>
                </div>
              );
            })}
          </div>
        ) : null}

        {activeSubject != null ? (
          <p className="mt-6 text-center text-xs text-subtle">{t("subjectHint")}</p>
        ) : null}
      </div>
    </ProtectedShell>
  );
}