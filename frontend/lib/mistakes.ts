import { api } from "./api";

export interface MistakeItem {
  question_id: number;
  text_uz: string;
  text_ru: string;
  text_en: string;
  subject_id: number | null;
  subject_name_uz: string | null;
  subject_name_ru: string | null;
  subject_name_en: string | null;
  wrong: number;
  last_wrong_at: string;
  is_mastered: boolean;
}

export interface MistakesResponse {
  total: number;
  count: number;
  items: MistakeItem[];
}

// A single practice session is capped at 30 questions by the API.
export const MISTAKE_SESSION_LIMIT = 30;

export function fetchMistakes(): Promise<MistakesResponse> {
  return api<MistakesResponse>("/stats/mistakes/");
}
