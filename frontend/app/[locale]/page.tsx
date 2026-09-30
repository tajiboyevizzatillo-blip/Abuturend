import { getTranslations, setRequestLocale } from "next-intl/server";
import Image from "next/image";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Link } from "@/i18n/navigation";
import { Reveal } from "@/components/landing/reveal";
import { Testimonials } from "@/components/landing/testimonials";
import { SubjectsGrid } from "@/components/landing/subjects-grid";
import { Leaderboard } from "@/components/landing/leaderboard";
import {
  AnalyticsMockup,
  ExamAppMockup,
  PHOTOS,
  StudyMockup,
} from "@/components/landing/illustrations";

const STATS = [
  { key: "statsStudents", value: "12 000+", icon: "users" },
  { key: "statsQuestions", value: "25 000+", icon: "book" },
  { key: "statsExams", value: "120+", icon: "clock" },
  { key: "statsUniversities", value: "40+", icon: "building" },
] as const;

const CAMPUSES = [
  "Toshkent Davlat Texnika",
  "TATU",
  "O‘zMU",
  "TDTU",
  "Buxoro",
  "Samarqand",
  "Nukus",
  "Andijon",
] as const;

const UNIVERSITIES = ["ToshDTU", "TATU", "O‘zMU", "TDTU", "BuxDU", "SamDU"];

function Icon({ name, size = 22 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    users: <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />,
    book: <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15A2.5 2.5 0 0 0 6.5 22H20V20H6.5A2.5 2.5 0 0 1 4 17.5z" />,
    clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
    building: <><rect x="4" y="2" width="16" height="20" rx="2" /><path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M8 10h.01M16 10h.01M12 10h.01M8 14h.01M16 14h.01M12 14h.01" /></>,
    pencil: <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />,
    timer: <><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2 2M9 2h6" /></>,
    chart: <><path d="M3 3v18h18" /><rect x="7" y="12" width="3" height="6" /><rect x="12" y="8" width="3" height="10" /><rect x="17" y="4" width="3" height="14" /></>,
    check: <path d="M20 6 9 17l-5-5" />,
    rocket: <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09zM12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2zM9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />,
    checkCircle: <><circle cx="12" cy="12" r="10" /><path d="m8.5 12 2.5 2.5 5-5" /></>,
    sparkles: <><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" /><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z" /></>,
    arrowRight: <path d="M5 12h14m-6-6 6 6-6 6" />,
    command: <><rect x="3" y="3" width="18" height="18" rx="6" /><circle cx="9" cy="9" r="1.5" /><circle cx="15" cy="15" r="1.5" /><path d="M9 15h6M15 9H9" /></>,
    layers: <path d="m12 2 9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5" />,
    bolt: <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z" />,
    target: <><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></>,
    compass: <><circle cx="12" cy="12" r="10" /><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" /></>,
    trending: <><polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" /></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
    cap: <><path d="M22 10 12 5 2 10l10 5 10-5z" /><path d="M6 12v5c0 1.5 3 3 6 3s6-1.5 6-3v-5" /></>,
    search: <><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></>,
    play: <polygon points="6 3 20 12 6 21 6 3" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {paths[name]}
    </svg>
  );
}

export default async function LandingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("landing");

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: "Abiturend",
    url: "https://abituriyent.orgtrace.uz",
    applicationCategory: "EducationalApplication",
    operatingSystem: "Any",
    availableLanguage: ["uz", "ru", "en"],
    description: t("heroSubtitle"),
    about: {
      "@type": "Organization",
      name: "Abiturend",
      description: t("heroSubtitle"),
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <Header />

      <main className="page-enter flex-1 overflow-x-clip">
        {/* ============ HERO ============ */}
        <section className="mesh noise-overlay relative">
          <div aria-hidden className="orb orb-blue anim-orb left-[-7rem] top-10 h-80 w-80" />
          <div aria-hidden className="orb orb-violet anim-orb-late right-[-6rem] top-24 h-96 w-96" />
          <div aria-hidden className="hero-grid absolute inset-0 -z-10" />

          <div className="relative z-10 mx-auto max-w-7xl px-4 pb-20 pt-16 sm:px-6 sm:pt-24">
            <Reveal className="text-center">
              <span className="glass inline-flex items-center gap-2.5 rounded-full px-4 py-2 text-sm font-semibold text-muted">
                <span className="live-dot" />
                {t("badge")}
              </span>
              <h1 className="text-display mx-auto mt-7 max-w-5xl text-balance">
                {t("heroTitle")}
                <span className="text-gradient block">{t("heroHighlight")}</span>
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-muted sm:text-xl">
                {t("heroSubtitle")}
              </p>
            </Reveal>

            <Reveal delay={120}>
              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link
                  href="/register"
                  className="btn btn-cta btn-lg cta-glow w-full px-8 py-3.5 text-base sm:w-auto"
                >
                  <Icon name="rocket" size={18} />
                  {t("ctaStart")}
                </Link>
                <Link
                  href="/login"
                  className="btn btn-secondary btn-lg w-full border-border-strong bg-surface/60 px-8 py-3.5 text-base backdrop-blur-sm sm:w-auto"
                >
                  {t("ctaLogin")}
                </Link>
              </div>
              <p className="mt-6 flex items-center justify-center gap-2 text-sm text-subtle">
                <Icon name="checkCircle" size={16} />
                {t("heroProof")}
              </p>
            </Reveal>

            {/* Product shot */}
            <Reveal delay={220}>
              <div className="relative mx-auto mt-16 max-w-5xl">
                <div aria-hidden className="orb orb-blue -inset-10 absolute opacity-70" />
                <div className="screen glass relative z-10 !border-transparent ring-1 ring-black/5 dark:ring-white/10">
                  <ExamAppMockup className="h-auto w-full" />
                </div>

                {/* Floating stat chips */}
                <div className="glass-strong anim-float absolute -left-3 top-10 hidden items-center gap-3 rounded-2xl px-4 py-3 sm:flex lg:-left-12">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary">
                    <Icon name="trending" size={19} />
                  </span>
                  <div className="flex flex-col">
                    <span className="text-base font-bold leading-tight tabular-nums">+27%</span>
                    <span className="text-xs text-muted">{t("statsQuestions")}</span>
                  </div>
                </div>
                <div className="glass-strong anim-float-slow absolute -right-3 bottom-16 hidden items-center gap-3 rounded-2xl px-4 py-3 sm:flex lg:-right-10">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-success-soft text-success">
                    <Icon name="checkCircle" size={19} />
                  </span>
                  <div className="flex flex-col">
                    <span className="text-base font-bold leading-tight">87%</span>
                    <span className="text-xs text-muted">{t("statsExams")}</span>
                  </div>
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        {/* ============ TRUST MARQUEE ============ */}
        <section className="border-y border-border bg-surface-subtle/40 py-7">
          <div className="marquee">
            <div className="marquee-track">
              {[...CAMPUSES, ...CAMPUSES].map((c, i) => (
                <span
                  key={`${c}-${i}`}
                  className="whitespace-nowrap text-sm font-bold uppercase tracking-[0.18em] text-subtle"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* ============ STATS ============ */}
        <section className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6">
          <Reveal>
            <div className="glass-strong -mt-8 grid grid-cols-2 gap-4 rounded-[1.75rem] p-6 sm:mt-0 sm:grid-cols-4 sm:p-8">
              {STATS.map((s, i) => (
                <div key={s.key} className="flex flex-col items-center px-2 text-center">
                  <div
                    className={`mb-2.5 flex h-11 w-11 items-center justify-center rounded-2xl ${
                      i % 2 ? "bg-accent-soft text-accent" : "bg-primary-soft text-primary"
                    }`}
                  >
                    <Icon name={s.icon} size={20} />
                  </div>
                  <p className="text-3xl font-extrabold tabular-nums tracking-tight">
                    {s.value}
                  </p>
                  <p className="mt-1 text-sm font-medium text-muted">{t(s.key)}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </section>

        {/* ============ BENTO FEATURES ============ */}
        <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6">
          <Reveal>
            <div className="mx-auto mb-14 max-w-2xl text-center">
              <span className="badge badge-primary mb-4">
                <Icon name="sparkles" size={15} />
                {t("badgeShort")}
              </span>
              <h2 className="text-display-sm text-balance">{t("featuresTitle")}</h2>
              <p className="mt-4 text-lg text-muted">{t("featuresSubtitle")}</p>
            </div>
          </Reveal>

          <div className="bento">
            {/* Practice — large tile with live mockup */}
            <Reveal className="bento-md">
              <div className="bento-card h-full p-7 sm:p-8">
                <div className="flex items-start gap-4">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                    <Icon name="pencil" size={22} />
                  </span>
                  <div>
                    <h3 className="text-xl font-bold tracking-tight">{t("featPracticeTitle")}</h3>
                    <p className="mt-1.5 text-sm leading-6 text-muted">{t("featPracticeDesc")}</p>
                  </div>
                </div>
                <div className="mt-6 overflow-hidden rounded-2xl border border-border bg-surface-subtle/60">
                  <StudyMockup className="h-auto w-full" />
                </div>
              </div>
            </Reveal>

            {/* Mock exam — dark accent tile */}
            <Reveal delay={90} className="bento-xs">
              <div className="bento-card h-full bg-gradient-to-br from-indigo-600 to-violet-700 p-7 dark:from-indigo-800 dark:to-violet-900">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15 text-white">
                  <Icon name="timer" size={22} />
                </div>
                <h3 className="mt-5 text-xl font-bold tracking-tight text-white">
                  {t("featExamTitle")}
                </h3>
                <p className="mt-1.5 text-sm leading-6 text-white/75">{t("featExamDesc")}</p>
                <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-white/15 px-3.5 py-1.5 text-xs font-semibold text-white">
                  <Icon name="bolt" size={14} />
                  {t("featExamChip")}
                </div>
              </div>
            </Reveal>

            {/* Analytics */}
            <Reveal delay={140} className="bento-xs">
              <div className="bento-card h-full p-7">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-info-soft text-info">
                  <Icon name="chart" size={22} />
                </div>
                <h3 className="mt-5 text-xl font-bold tracking-tight">{t("featAnalyticsTitle")}</h3>
                <p className="mt-1.5 text-sm leading-6 text-muted">{t("featAnalyticsDesc")}</p>
                <div className="mt-6 flex items-end gap-1.5">
                  {[34, 52, 44, 66, 58, 80].map((h, i) => (
                    <span
                      key={i}
                      className={`w-full rounded-md bg-gradient-to-t ${
                        i === 5 ? "from-info to-info/40" : "from-info/70 to-info/25"
                      }`}
                      style={{ height: `${h * 0.55}px` }}
                    />
                  ))}
                </div>
              </div>
            </Reveal>

            {/* University */}
            <Reveal delay={190} className="bento-xs">
              <div className="bento-card h-full p-7">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                  <Icon name="cap" size={22} />
                </div>
                <h3 className="mt-5 text-xl font-bold tracking-tight">{t("featUniTitle")}</h3>
                <p className="mt-1.5 text-sm leading-6 text-muted">{t("featUniDesc")}</p>
                <div className="mt-6 flex flex-wrap gap-2">
                  {UNIVERSITIES.map((u) => (
                    <span
                      key={u}
                      className="rounded-full border border-border bg-surface-subtle px-3 py-1 text-xs font-semibold text-muted"
                    >
                      {u}
                    </span>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        {/* ============ SUBJECTS ============ */}
        <div className="border-t border-border bg-surface-subtle/40">
          <SubjectsGrid />
        </div>

        {/* ============ SHOWCASE — Practice ============ */}
        <section className="relative py-24">
          <div aria-hidden className="orb orb-blue right-[-8rem] top-20 h-80 w-80 opacity-60" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6">
            <div className="grid items-center gap-12 lg:grid-cols-2">
              <Reveal>
                <div className="screen relative">
                  <div aria-hidden className="orb orb-amber -inset-8 absolute opacity-60" />
                  <div className="screen z-10 border-transparent">
                    <StudyMockup className="h-auto w-full" />
                  </div>
                </div>
              </Reveal>
              <Reveal delay={120}>
                <div>
                  <span className="badge badge-primary mb-4">
                    <Icon name="pencil" size={15} />
                    {t("showcasePracticeTag")}
                  </span>
                  <h3 className="text-3xl font-bold tracking-tight sm:text-4xl">
                    {t("showcasePracticeTitle")}
                  </h3>
                  <p className="mt-4 text-lg leading-7 text-muted">
                    {t("showcasePracticeDesc")}
                  </p>
                  <ul className="mt-7 flex flex-col gap-3.5">
                    {[1, 2, 3].map((i) => (
                      <li key={i} className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-success-soft text-success">
                          <Icon name="checkCircle" size={15} />
                        </span>
                        <span className="font-medium">{t(`showcasePracticeP${i}`)}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href="/subjects" className="btn btn-cta btn-sm mt-9 px-6 py-2.5">
                    {t("ctaStart")}
                    <Icon name="arrowRight" size={16} />
                  </Link>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* ============ SHOWCASE — Analytics ============ */}
        <section className="border-t border-border bg-surface-subtle/50">
          <div className="mx-auto max-w-7xl px-4 py-24 sm:px-6">
            <div className="grid items-center gap-12 lg:grid-cols-2">
              <Reveal className="lg:order-2">
                <div className="screen relative">
                  <div aria-hidden className="orb orb-violet -inset-8 absolute opacity-60" />
                  <div className="screen z-10 border-transparent">
                    <AnalyticsMockup className="h-auto w-full" />
                  </div>
                </div>
              </Reveal>
              <Reveal delay={120} className="lg:order-1">
                <div>
                  <span className="badge badge-info mb-4">
                    <Icon name="chart" size={15} />
                    {t("showcaseAnalyticsTag")}
                  </span>
                  <h3 className="text-3xl font-bold tracking-tight sm:text-4xl">
                    {t("showcaseAnalyticsTitle")}
                  </h3>
                  <p className="mt-4 text-lg leading-7 text-muted">
                    {t("showcaseAnalyticsDesc")}
                  </p>
                  <ul className="mt-7 flex flex-col gap-3.5">
                    {[1, 2, 3].map((i) => (
                      <li key={i} className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-success-soft text-success">
                          <Icon name="checkCircle" size={15} />
                        </span>
                        <span className="font-medium">{t(`showcaseAnalyticsP${i}`)}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href="/register" className="btn btn-cta btn-sm mt-9 px-6 py-2.5">
                    {t("ctaStart")}
                    <Icon name="arrowRight" size={16} />
                  </Link>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* ============ UNIVERSITIES ============ */}
        <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6">
          <Reveal>
            <div className="bento-card mesh relative overflow-hidden p-10 sm:p-14">
              <div aria-hidden className="orb orb-violet right-[-6rem] top-[-6rem] h-72 w-72 opacity-60" />
              <div className="relative z-10 flex flex-col items-start gap-8 lg:flex-row lg:items-center lg:justify-between">
                <div className="max-w-xl">
                  <span className="badge badge-primary mb-4">
                    <Icon name="cap" size={15} />
                    {t("uniTag")}
                  </span>
                  <h2 className="text-display-sm text-balance">{t("uniTitle")}</h2>
                  <p className="mt-4 text-lg text-muted">{t("uniSubtitle")}</p>
                </div>
                <div className="flex w-full flex-col items-start gap-5 lg:w-auto lg:items-end">
                  <div className="grid w-full grid-cols-2 gap-2 sm:grid-cols-3 lg:w-64">
                    {UNIVERSITIES.map((u) => (
                      <span
                        key={u}
                        className="rounded-xl border border-border bg-surface/80 px-3 py-2.5 text-center text-xs font-semibold text-muted backdrop-blur-sm"
                      >
                        {u}
                      </span>
                    ))}
                  </div>
                  <Link href="/universities" className="btn btn-cta px-6 py-2.5">
                    {t("uniCta")}
                    <Icon name="arrowRight" size={16} />
                  </Link>
                </div>
              </div>
            </div>
          </Reveal>
        </section>

        {/* ============ WHY US — photo pillars ============ */}
        <section className="relative py-24">
          <div aria-hidden className="orb orb-violet left-[-8rem] top-1/3 h-80 w-80 opacity-50" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6">
            <Reveal>
              <div className="mx-auto mb-14 max-w-2xl text-center">
                <span className="badge badge-warning mb-4">
                  <Icon name="sparkles" size={15} />
                  {t("whyTag")}
                </span>
                <h2 className="text-display-sm text-balance">{t("whyTitle")}</h2>
                <p className="mt-4 text-lg text-muted">{t("whySubtitle")}</p>
              </div>
            </Reveal>

            <div className="grid gap-6 md:grid-cols-2">
              {(
                [
                  { img: PHOTOS.bank, key: "1" },
                  { img: PHOTOS.conditions, key: "2" },
                  { img: PHOTOS.analytics, key: "3" },
                  { img: PHOTOS.mentor, key: "4" },
                ] as const
              ).map((card, i) => (
                <Reveal key={card.key} delay={i * 90}>
                  <article className="bento-card group h-full overflow-hidden">
                    <div className="relative h-52 overflow-hidden sm:h-60">
                      <Image
                        src={card.img}
                        alt=""
                        fill
                        className="object-cover transition-transform duration-700 ease-out group-hover:scale-105"
                        sizes="(max-width: 768px) 100vw, 50vw"
                      />
                      <div
                        aria-hidden
                        className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent"
                      />
                      <div className="absolute bottom-4 left-5 flex items-center gap-3">
                        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15 text-lg font-extrabold text-white backdrop-blur-md ring-1 ring-white/25">
                          {card.key}
                        </span>
                        <h3 className="text-lg font-bold text-white drop-shadow">
                          {t(`why${card.key}Title`)}
                        </h3>
                      </div>
                    </div>
                    <div className="p-6">
                      <p className="text-[15px] leading-7 text-muted">{t(`why${card.key}Desc`)}</p>
                    </div>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ============ HOW IT WORKS ============ */}
        <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6">
          <Reveal>
            <div className="mx-auto mb-16 max-w-2xl text-center">
              <h2 className="text-display-sm text-balance">{t("howItWorksTitle")}</h2>
              <p className="mt-4 text-lg text-muted">{t("howItWorksSubtitle")}</p>
            </div>
          </Reveal>
          <div className="grid gap-6 md:grid-cols-3">
            {([1, 2, 3] as const).map((step, i) => (
              <Reveal key={step} delay={i * 120}>
                <div className="bento-card relative p-8">
                  <span aria-hidden className="ghost-num absolute right-6 top-4">
                    0{step}
                  </span>
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-700 text-lg font-bold text-white shadow-raised">
                    {step}
                  </span>
                  <h3 className="mt-5 text-xl font-bold tracking-tight">{t(`step${step}Title`)}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted">{t(`step${step}Desc`)}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ============ TESTIMONIALS ============ */}
        <Testimonials />

        {/* ============ LEADERBOARD ============ */}
        <Leaderboard />

        {/* ============ FINAL CTA ============ */}
        <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
          <Reveal>
            <div className="mesh noise-overlay relative overflow-hidden rounded-[2rem] border border-border p-10 text-center sm:p-16">
              <div aria-hidden className="orb orb-blue left-[-4rem] top-[-4rem] h-72 w-72 opacity-70" />
              <div aria-hidden className="orb orb-amber bottom-[-5rem] right-[-3rem] h-72 w-72 opacity-60" />
              <div className="relative z-10 flex flex-col items-center gap-6">
                <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-700 text-white shadow-raised">
                  <Icon name="target" size={26} />
                </span>
                <p className="font-serif text-xl italic text-muted sm:text-2xl">
                  {t("heroTagline")}
                </p>
                <h2 className="text-display-sm max-w-2xl text-balance">{t("ctaTitle")}</h2>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Link href="/register" className="btn btn-cta btn-lg cta-glow px-8 py-3.5">
                    <Icon name="rocket" size={18} />
                    {t("ctaStart")}
                  </Link>
                  <Link
                    href="/login"
                    className="btn btn-secondary btn-lg border-border-strong bg-surface px-8 py-3.5"
                  >
                    {t("ctaLogin")}
                  </Link>
                </div>
              </div>
            </div>
          </Reveal>
        </section>
      </main>

      <Footer />
    </>
  );
}
