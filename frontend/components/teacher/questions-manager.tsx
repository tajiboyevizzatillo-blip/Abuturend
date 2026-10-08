"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, extractFieldError } from "@/lib/api";
import { fetchSubjects, localizedName, type Subject } from "@/lib/catalog";
import {
  createQuestion,
  deleteQuestion,
  fetchQuestions,
  updateQuestion,
  type Difficulty,
  type Question,
  type QuestionInput,
  type QuestionStatus,
} from "@/lib/questions";
import { cn } from "@/lib/utils";

interface OptionDraft {
  id?: number;
  text_uz: string;
  is_correct: boolean;
  sort_order?: number;
}

interface FormState {
  subject: string;
  text_uz: string;
  question_type: "single" | "multiple";
  difficulty: Difficulty;
  explanation_uz: string;
  status: QuestionStatus;
  options: OptionDraft[];
}

const EMPTY_FORM: FormState = {
  subject: "",
  text_uz: "",
  question_type: "single",
  difficulty: 2,
  explanation_uz: "",
  status: "draft",
  options: [
    { text_uz: "", is_correct: false },
    { text_uz: "", is_correct: false },
    { text_uz: "", is_correct: false },
    { text_uz: "", is_correct: false },
  ],
};

function difficultyKey(d: number): string {
  return d === 1 ? "difficultyEasy" : d === 3 ? "difficultyHard" : "difficultyMedium";
}

export function QuestionsManager() {
  const t = useTranslations("teacher");
  const common = useTranslations("common");
  const locale = useLocale();
  // Question bank content is authored in uz with optional ru/en translations;
  // the list shows whichever translation exists for the active locale.
  const displayText = (uz: string, ru?: string | null, en?: string | null) =>
    locale === "ru" ? ru || uz : locale === "en" ? en || uz : uz;

  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [filterStatus, setFilterStatus] = useState<QuestionStatus | "">("");
  const [filterSubject, setFilterSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  // Explicit open/closed state. It used to be derived from the form contents
  // (`editingId !== null || form.text_uz !== ""`), which meant "New question"
  // set editingId to null and an empty text_uz — so formOpen was false, the form
  // never rendered, and creating a question was unreachable from the UI.
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const load = () => {
    Promise.all([
      fetchSubjects(),
      fetchQuestions({
        subject: filterSubject ? Number(filterSubject) : undefined,
        status: filterStatus || undefined,
      }),
    ])
      .then(([subs, qs]) => {
        setSubjects(subs);
        setQuestions(qs);
      })
      .catch(() => setError(common("error")));
  };

  useEffect(() => {
    let ignore = false;
    Promise.all([
      fetchSubjects(),
      fetchQuestions({
        subject: filterSubject ? Number(filterSubject) : undefined,
        status: filterStatus || undefined,
      }),
    ])
      .then(([subs, qs]) => {
        if (!ignore) {
          setError(null);
          setSubjects(subs);
          setQuestions(qs);
        }
      })
      .catch(() => {
        if (!ignore) setError(common("error"));
      });
    return () => {
      ignore = true;
    };
  }, [filterStatus, filterSubject, common]);

  const subjectsById = useMemo(() => {
    const map = new Map<number, Subject>();
    (subjects ?? []).forEach((s) => map.set(s.id, s));
    return map;
  }, [subjects]);

  const startCreate = () => {
    setEditingId(null);
    setCreating(true);
    setForm({
      ...EMPTY_FORM,
      subject: filterSubject || (subjects && subjects[0] ? String(subjects[0].id) : ""),
    });
  };

  const startEdit = (q: Question) => {
    setEditingId(q.id);
    setCreating(false);
    setForm({
      subject: String(q.subject),
      text_uz: q.text_uz,
      question_type: q.question_type,
      difficulty: q.difficulty as Difficulty,
      explanation_uz: q.explanation_uz,
      status: q.status,
      options: q.options.map((o) => ({
        id: o.id,
        text_uz: o.text_uz,
        is_correct: o.is_correct,
        sort_order: o.sort_order,
      })),
    });
  };

  const setOption = (index: number, patch: Partial<OptionDraft>) => {
    setForm((f) => ({
      ...f,
      options: f.options.map((o, i) => (i === index ? { ...o, ...patch } : o)),
    }));
  };

  const toggleSingle = (index: number) => {
    setForm((f) => ({
      ...f,
      options: f.options.map((o, i) => ({ ...o, is_correct: i === index })),
    }));
  };

  const removeOption = (index: number) => {
    setForm((f) => ({
      ...f,
      options: f.options.filter((_, i) => i !== index),
    }));
  };

  const addOption = () => {
    setForm((f) => ({ ...f, options: [...f.options, { text_uz: "", is_correct: false }] }));
  };

  const save = async () => {
    setError(null);
    if (!form.subject) {
      setError(common("error"));
      return;
    }
    const input: QuestionInput = {
      subject: Number(form.subject),
      topic: null,
      text_uz: form.text_uz,
      question_type: form.question_type,
      difficulty: form.difficulty,
      explanation_uz: form.explanation_uz,
      source_type: "custom",
      status: form.status,
      options: form.options
        .filter((o) => o.text_uz.trim().length > 0)
        .map((o, i) => ({ ...o, sort_order: i })),
    };
    setSaving(true);
    try {
      if (editingId === null) {
        await createQuestion(input);
      } else {
        await updateQuestion(editingId, input);
      }
      setEditingId(null);
      setCreating(false);
      setForm(EMPTY_FORM);
      load();
    } catch (e) {
      setError(
        e instanceof ApiError
          ? extractFieldError(e.detail) ?? e.message
          : common("error")
      );
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (q: Question, status: QuestionStatus) => {
    try {
      await updateQuestion(q.id, { status });
      load();
    } catch {
      setError(common("error"));
    }
  };

  const remove = async (q: Question) => {
    if (!window.confirm(t("questions.confirmDelete"))) return;
    try {
      await deleteQuestion(q.id);
      load();
    } catch {
      setError(common("error"));
    }
  };

  const formOpen = creating || editingId !== null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">{t("questions.title")}</h1>
          <p className="font-serif italic text-subtle">{t("questions.subtitle")}</p>
        </div>
        <button type="button" className="btn btn-primary btn-sm" onClick={startCreate}>
          + {t("questions.new")}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select
          className="input input-sm"
          value={filterSubject}
          onChange={(e) => setFilterSubject(e.target.value)}
          aria-label={t("questions.allSubjects")}
        >
          <option value="">{t("questions.allSubjects")}</option>
          {(subjects ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {localizedName(s, locale)}
            </option>
          ))}
        </select>
        <select
          className="input input-sm"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value as QuestionStatus | "")}
          aria-label={t("questions.allStatuses")}
        >
          <option value="">{t("questions.allStatuses")}</option>
          <option value="draft">{t("questions.statusDraft")}</option>
          <option value="published">{t("questions.statusPublished")}</option>
          <option value="archived">{t("questions.statusArchived")}</option>
        </select>
      </div>

      {error ? <Alert variant="danger">{error}</Alert> : null}

      {formOpen ? (
        <Card className="flex flex-col gap-4 p-6">
          <h2 className="text-xl font-semibold">
            {editingId === null ? t("questions.new") : `${t("questions.edit")} #${editingId}`}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label className="label" htmlFor="qm-subject">{t("questions.subject")}</label>
              <select
                id="qm-subject"
                className="input"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
              >
                <option value="">{common("none")}</option>
                {(subjects ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {localizedName(s, locale)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="label" htmlFor="qm-difficulty">{t("questions.difficulty")}</label>
              <select
                id="qm-difficulty"
                className="input"
                value={form.difficulty}
                onChange={(e) =>
                  setForm({ ...form, difficulty: Number(e.target.value) as Difficulty })
                }
              >
                <option value={1}>{t("questions.difficultyEasy")}</option>
                <option value={2}>{t("questions.difficultyMedium")}</option>
                <option value={3}>{t("questions.difficultyHard")}</option>
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="qm-text">{t("questions.text")}</label>
            <textarea
              id="qm-text"
              className="input min-h-[90px]"
              value={form.text_uz}
              onChange={(e) => setForm({ ...form, text_uz: e.target.value })}
              placeholder={t("questions.textHint")}
            />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="label">{t("questions.options")}</label>
              <div className="flex items-center gap-2">
                <select
                  className="input input-sm"
                  value={form.question_type}
                  aria-label={t("questions.options")}
                  onChange={(e) =>
                    setForm({ ...form, question_type: e.target.value as "single" | "multiple" })
                  }
                >
                  <option value="single">{t("questions.single")}</option>
                  <option value="multiple">{t("questions.multiple")}</option>
                </select>
                <button type="button" className="btn btn-secondary btn-sm" onClick={addOption}>
                  + {t("questions.addOption")}
                </button>
              </div>
            </div>
            {form.options.length === 0 ? (
              <p className="text-sm text-subtle">{common("none")}</p>
            ) : (
              <div className="flex flex-col gap-2">
                {form.options.map((opt, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="accent-primary"
                      checked={opt.is_correct}
                      onChange={() =>
                        form.question_type === "single"
                          ? toggleSingle(i)
                          : setOption(i, { is_correct: !opt.is_correct })
                      }
                      aria-label={t("questions.correct")}
                    />
                    <input
                      className="input input-sm flex-1"
                      value={opt.text_uz}
                      placeholder={`${t("questions.option")} ${String.fromCharCode(65 + i)}`}
                      aria-label={`${t("questions.option")} ${String.fromCharCode(65 + i)}`}
                      onChange={(e) => setOption(i, { text_uz: e.target.value })}
                    />
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => removeOption(i)}
                      aria-label={`${t("questions.delete")} ${String.fromCharCode(65 + i)}`}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="qm-explanation">{t("questions.explanation")}</label>
            <textarea
              id="qm-explanation"
              className="input min-h-[70px]"
              value={form.explanation_uz}
              onChange={(e) => setForm({ ...form, explanation_uz: e.target.value })}
              placeholder={t("questions.explanationHint")}
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="btn btn-primary"
              disabled={saving}
              onClick={save}
            >
              {saving ? common("loading") : common("save")}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setEditingId(null);
                setCreating(false);
                setForm(EMPTY_FORM);
              }}
            >
              {common("cancel")}
            </button>
          </div>
        </Card>
      ) : null}

      {!questions ? (
        <div className="grid gap-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : questions.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 p-14 text-center">
          <p className="text-muted">{common("empty")}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {questions.map((q) => (
            <Card key={q.id} className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-subtle">#{q.id}</span>
                    <Badge>
                      {(() => {
                        const s = subjectsById.get(q.subject);
                        return s ? localizedName(s, locale) : String(q.subject);
                      })()}
                    </Badge>
                    <Badge>{t(`questions.${difficultyKey(q.difficulty)}`)}</Badge>
                    <Badge
                      variant={
                        q.status === "published"
                          ? "success"
                          : q.status === "archived"
                            ? "neutral"
                            : "warning"
                      }
                    >
                      {q.status === "published"
                        ? t("questions.statusPublished")
                        : q.status === "archived"
                          ? t("questions.statusArchived")
                          : t("questions.statusDraft")}
                    </Badge>
                  </div>
                  <p className="font-medium">{displayText(q.text_uz, q.text_ru, q.text_en)}</p>
                  <p className="mt-1 flex flex-wrap gap-2 text-xs text-subtle">
                    {q.options.map((o, i) => (
                      <span key={i} className={cn(o.is_correct && "font-semibold text-success")}>
                        {String.fromCharCode(65 + i)}. {displayText(o.text_uz, o.text_ru, o.text_en)}
                      </span>
                    ))}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => startEdit(q)}>
                    {t("questions.edit")}
                  </button>
                  {q.status === "draft" ? (
                    <button
                      type="button"
                      className="btn btn-success btn-sm"
                      onClick={() => setStatus(q, "published")}
                    >
                      {t("questions.publish")}
                    </button>
                  ) : q.status === "published" ? (
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => setStatus(q, "archived")}>
                      {t("questions.archive")}
                    </button>
                  ) : null}
                  <button type="button" className="btn btn-danger btn-sm" onClick={() => remove(q)}>
                    {t("questions.delete")}
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}