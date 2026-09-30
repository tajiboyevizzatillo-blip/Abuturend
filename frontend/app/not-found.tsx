import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

export default function NotFound() {
  const t = useTranslations("common");
  return (
    <main className="hero-bg relative flex min-h-screen flex-col items-center justify-center gap-2 overflow-hidden bg-background px-4 text-center">
      <div className="hero-glow" aria-hidden />
      <p className="font-serif italic bg-gradient-to-r from-primary to-accent bg-clip-text text-7xl font-bold text-transparent">
        404
      </p>
      <h1 className="pt-2 text-h2 font-extrabold tracking-tight">{t("notFoundTitle")}</h1>
      <p className="text-muted">{t("notFoundDesc")}</p>
      <Link
        href="/"
        className="btn btn-primary btn-lg mt-4"
      >
        {t("back")}
      </Link>
    </main>
  );
}