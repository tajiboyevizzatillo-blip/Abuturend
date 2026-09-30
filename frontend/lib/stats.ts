import { api } from "./api";

export interface WeekActivityDay {
  date: string;
  answered: number;
  correct: number;
}

export interface SubjectBreakdown {
  subject_id: number;
  subject_name_uz: string;
  subject_name_ru: string;
  subject_name_en: string;
  slug: string;
  sessions: number;
  questions: number;
  correct: number;
  accuracy: number;
}

export interface WeakTopic {
  topic_id: number;
  topic_name_uz: string;
  topic_name_ru: string;
  topic_name_en: string;
  subject_name_uz: string;
  subject_name_ru: string;
  subject_name_en: string;
  wrong: number;
}

export interface RecentSession {
  id: number;
  mode: "practice" | "exam";
  status: "in_progress" | "finished";
  subject: null | { id: number; name_uz: string; name_ru: string; name_en: string; slug: string };
  question_count: number;
  progress_index: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered: number;
  score_percent: number;
  started_at: string;
  finished_at: string | null;
}

export interface StatsSummary {
  total_finished: number;
  total_questions: number;
  total_answered: number;
  accuracy: number;
  current_score: number;
  streak: number;
  weekly_activity: WeekActivityDay[];
  subject_breakdown: SubjectBreakdown[];
  weak_topics: WeakTopic[];
  recent_sessions: RecentSession[];
}

export async function fetchStatsSummary(): Promise<StatsSummary> {
  return api<StatsSummary>("/stats/summary/");
}