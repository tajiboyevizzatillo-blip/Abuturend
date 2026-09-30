import { api } from "./api";

/** A subject spoke of the radar (one axis). */
export interface RadarSubject {
  subject_id: number;
  slug: string;
  subject_name_uz: string;
  subject_name_ru: string;
  subject_name_en: string;
  answered: number;
  correct: number;
  /** Accuracy 0-100. */
  accuracy: number;
  /** false -> not enough answers to trust the number yet. */
  enough_data: boolean;
  last_answered_at: string | null;
}

/** One topic with its accuracy, wrong count and drill state. */
export interface WeakTopic {
  topic_id: number | null;
  topic_name_uz: string;
  topic_name_ru: string;
  topic_name_en: string;
  /** true -> question has no topic and lands in the virtual "Boshqa" bucket. */
  is_other: boolean;
  subject_id: number | null;
  answered: number;
  correct: number;
  wrong: number;
  accuracy: number;
  last_answered_at: string | null;
  enough_data: boolean;
  is_weak: boolean;
}

/** PRO-only per-day accuracy of a topic. */
export interface TopicHistoryPoint {
  topic_id: number | null;
  topic_name_uz: string;
  day: string;
  answered: number;
  accuracy: number;
}

export interface WeakSkillsRules {
  /** Accuracy below this counts as weak. */
  threshold: number;
  /** Answers a topic needs before it is judged at all. */
  min_answers: number;
  topic_limit: number;
  free_topic_limit: number;
  is_premium: boolean;
}

export interface WeakSkillsResponse extends WeakSkillsRules {
  subjects: RadarSubject[];
  weak_topics: WeakTopic[];
  /** Weak topics hidden behind the PRO paywall (free tier). */
  hidden_weak_topics: number;
  can_practice: boolean;
  has_data: boolean;
}

export interface WeakSkillSubjectResponse extends WeakSkillsRules {
  subject: {
    subject_id: number;
    slug: string;
    subject_name_uz: string;
    subject_name_ru: string;
    subject_name_en: string;
  };
  topics: WeakTopic[];
  weak_topic_ids: number[];
  hidden_weak_topics: number;
  can_practice: boolean;
  has_data: boolean;
  history?: TopicHistoryPoint[];
}

/** Session payload returned by the practice endpoint (same shape as /sessions/). */
export interface WeakPracticeSession {
  id: number;
  question_count: number;
  subject: number | null;
  current_question: unknown | null;
}

export function fetchWeakSkills(): Promise<WeakSkillsResponse> {
  return api<WeakSkillsResponse>("/weak-skills/");
}

/** `subject` may be an id or a slug - the API accepts both. */
export function fetchWeakSkillSubject(subject: number | string): Promise<WeakSkillSubjectResponse> {
  return api<WeakSkillSubjectResponse>(`/weak-skills/${subject}/`);
}

export function startWeakPractice(body: {
  topic_ids?: number[];
  subject?: number;
  question_count?: number;
}): Promise<WeakPracticeSession> {
  return api<WeakPracticeSession>("/weak-skills/practice/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Localized label for a topic row (falls back to Uzbek). */
export function topicName(
  topic: { topic_name_uz: string; topic_name_ru: string; topic_name_en: string },
  locale: string
): string {
  if (locale === "ru") return topic.topic_name_ru || topic.topic_name_uz;
  if (locale === "en") return topic.topic_name_en || topic.topic_name_uz;
  return topic.topic_name_uz;
}

/** Localized label for a radar axis. */
export function subjectName(
  subject: { subject_name_uz: string; subject_name_ru: string; subject_name_en: string },
  locale: string
): string {
  if (locale === "ru") return subject.subject_name_ru || subject.subject_name_uz;
  if (locale === "en") return subject.subject_name_en || subject.subject_name_uz;
  return subject.subject_name_uz;
}