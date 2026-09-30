import { api } from "./api";

export type OnboardingLevel = "beginner" | "middle" | "high";

export interface OnboardingSubjectBrief {
  id: number;
  slug: string;
  code: string;
  name_uz: string;
  name_ru: string;
  name_en: string;
}

export interface OnboardingTopicBrief {
  id: number;
  slug: string;
  subject_id: number;
  name_uz: string;
  name_ru: string;
  name_en: string;
}

export interface OnboardingDirectionBrief {
  id: number;
  code: string;
  name_uz: string;
  name_ru: string;
  name_en: string;
  university: {
    slug: string;
    name_uz: string;
    name_ru: string;
    name_en: string;
  };
}

export interface OnboardingProfile {
  id: number;
  direction: OnboardingDirectionBrief | null;
  subjects: OnboardingSubjectBrief[];
  exam_date: string | null;
  daily_minutes: number;
  level: OnboardingLevel;
  completed: boolean;
  skipped: boolean;
  days_left: number | null;
  needs_onboarding: boolean;
  created_at: string;
  updated_at: string;
}

export interface OnboardingStatus {
  completed: boolean;
  skipped: boolean;
  needs_onboarding: boolean;
  profile: OnboardingProfile;
  has_plan: boolean;
}

export interface PlanDayItem {
  subject_id: number;
  subject: OnboardingSubjectBrief | null;
  topic_id: number | null;
  topic: OnboardingTopicBrief | null;
  questions: number;
  minutes: number;
}

export interface PlanDay {
  day: number;
  date: string;
  questions: number;
  minutes: number;
  items: PlanDayItem[];
}

export interface OnboardingPlan {
  id: number;
  profile: OnboardingProfile;
  start_date: string;
  days: PlanDay[];
  total_questions: number;
  weak_subjects: OnboardingSubjectBrief[];
  /** 1-based index of today's plan day, null when the plan has ended. */
  today: number | null;
  created_at: string;
}

export interface OnboardingSubmitPayload {
  direction?: number | null;
  subjects: number[];
  exam_date?: string | null;
  daily_minutes: number;
  level: OnboardingLevel;
}

export const MIN_DAILY_MINUTES = 15;
export const MAX_DAILY_MINUTES = 480;

export function fetchOnboardingStatus(): Promise<OnboardingStatus> {
  return api<OnboardingStatus>("/onboarding/");
}

export function submitOnboarding(
  payload: OnboardingSubmitPayload
): Promise<OnboardingPlan> {
  return api<OnboardingPlan>("/onboarding/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchOnboardingPlan(): Promise<OnboardingPlan> {
  return api<OnboardingPlan>("/onboarding/plan/");
}

export function skipOnboarding(): Promise<OnboardingProfile> {
  return api<OnboardingProfile>("/onboarding/skip/", { method: "POST" });
}
