"use client";

import { useLocale, useTranslations } from "next-intl";
import type { SessionReport } from "@/lib/sessions";
import { cn } from "@/lib/utils";

/** Question-by-question review of a finished session (correct/wrong badge,
 * the student's answer, the correct answer and the explanation). Shared by
 * the exam finish screen and the `/results/[id]` review page. */
export function ReportList({ report }: { report: SessionReport | null }) {
  const t = useTranslations("exam");
  const locale = useLocale();
  if (!report) return null;
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-xl font-extrabold tracking-tight">{t("review")}</h3>
      {report.questions.map((row) => {
        const questionText =
          locale === "ru"
            ? row.question.text_ru || row.question.text_uz
            : locale === "en"
              ? row.question.text_en || row.question.text_uz
              : row.question.text_uz;
        const chosen = row.question.options.find((o) => o.id === row.selected_option_id);
        const correct = row.question.options.find((o) => o.is_correct);
        const chosenText =
          locale === "ru"
            ? chosen?.text_ru || chosen?.text_uz
            : locale === "en"
              ? chosen?.text_en || chosen?.text_uz
              : chosen?.text_uz;
        const correctText =
          locale === "ru"
            ? correct?.text_ru || correct?.text_uz
            : locale === "en"
              ? correct?.text_en || correct?.text_uz
              : correct?.text_uz;
        const unanswered = row.selected_option_id == null;
        const explanation =
          locale === "ru"
            ? row.question.explanation_ru || row.question.explanation_uz
            : locale === "en"
              ? row.question.explanation_en || row.question.explanation_uz
              : row.question.explanation_uz;
        return (
          <div key={row.question.id} className="card p-5">
            <div className="flex gap-3">
              {/* A skipped question is neither correct nor "wrong": labelling it
                  as a wrong answer hid how many were simply never reached. */}
              <span
                className={cn(
                  "badge",
                  unanswered ? "badge-neutral" : row.is_correct ? "badge-success" : "badge-danger"
                )}
              >
                {unanswered ? t("unanswered") : row.is_correct ? t("correctAnswer") : t("wrongAnswer")}
              </span>
            </div>
            <p className="mt-2 font-medium leading-relaxed">{questionText}</p>
            <div className="mt-3 flex flex-col gap-1.5 text-sm">
              <p className="text-subtle">
                {t("yourAnswer")}: <span className="font-semibold text-foreground">{chosenText ?? "—"}</span>
              </p>
              {!row.is_correct ? (
                <p className="text-subtle">
                  {t("correctAnswer")}: <span className="font-semibold text-success">{correctText ?? "—"}</span>
                </p>
              ) : null}
            </div>
            {explanation ? (
              <p className="mt-3 rounded-lg bg-surface-subtle p-3 text-sm text-muted">
                {t("explanation")}: {explanation}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
