import { api } from "./api";

export interface DirectionSubject {
  id: number;
  name_uz: string;
  name_ru: string;
  name_en: string;
  slug: string;
}

export interface Direction {
  id: number;
  name_uz: string;
  name_ru: string;
  name_en: string;
  code: string;
  university: {
    slug: string;
    name_uz: string;
    name_ru: string;
    name_en: string;
  };
  subjects: DirectionSubject[];
  duration_years: number | null;
  quota: number | null;
  grant_places: number | null;
  paid_places: number | null;
  is_active: boolean;
}

export interface University {
  id: number;
  slug: string;
  name_uz: string;
  name_ru: string;
  name_en: string;
  code: string;
  city_uz: string;
  city_ru: string;
  city_en: string;
  established: number | null;
  website: string;
  description_uz: string;
  description_ru: string;
  description_en: string;
  direction_count: number;
  directions?: Direction[];
}

export async function fetchUniversities(): Promise<University[]> {
  const data = await api<{ results: University[] }>("/universities/?page_size=100");
  return data.results;
}

export async function fetchUniversity(slug: string): Promise<University> {
  return api<University>(`/universities/${slug}/`);
}

export async function fetchDirections(params?: {
  university?: string;
  subject?: number;
}): Promise<Direction[]> {
  const qs = new URLSearchParams();
  if (params?.university) qs.set("university", params.university);
  if (params?.subject) qs.set("subject", String(params.subject));
  qs.set("page_size", "100");
  const data = await api<{ results: Direction[] }>(
    `/directions/?${qs.toString()}`
  );
  return data.results;
}

export function localizedUniversityName(u: Pick<University, "name_uz" | "name_ru" | "name_en">, locale: string): string {
  if (locale === "ru") return u.name_ru || u.name_uz;
  if (locale === "en") return u.name_en || u.name_uz;
  return u.name_uz;
}

export function localizedCity(u: Pick<University, "city_uz" | "city_ru" | "city_en">, locale: string): string {
  if (locale === "ru") return u.city_ru || u.city_uz;
  if (locale === "en") return u.city_en || u.city_uz;
  return u.city_uz;
}

export function localizedDirectionName(d: Pick<Direction, "name_uz" | "name_ru" | "name_en">, locale: string): string {
  if (locale === "ru") return d.name_ru || d.name_uz;
  if (locale === "en") return d.name_en || d.name_uz;
  return d.name_uz;
}

export function localizedSubjectName(s: DirectionSubject, locale: string): string {
  if (locale === "ru") return s.name_ru || s.name_uz;
  if (locale === "en") return s.name_en || s.name_uz;
  return s.name_uz;
}