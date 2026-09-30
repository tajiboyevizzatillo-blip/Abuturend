import { api } from "./api";

export type CertificateStyle = "international" | "local";

export interface Certificate {
  id: number;
  serial: string;
  style: CertificateStyle;
  full_name: string;
  score_percent: number;
  correct_answers: number;
  question_count: number;
  // International style: CEFR-ish band (A1..C1) computed server-side.
  grade: string;
  // Local style: 60%+ passes.
  passed: boolean;
  issued_at: string;
  exam_finished_at: string | null;
}

/** Issue a certificate for a finished unified exam (idempotent per style). */
export async function createCertificate(
  sessionId: number,
  style: CertificateStyle
): Promise<Certificate> {
  return api<Certificate>("/certificates/", {
    method: "POST",
    body: JSON.stringify({ session: sessionId, style }),
  });
}

/** The signed-in student's own certificates. */
export async function fetchCertificates(): Promise<Certificate[]> {
  return api<Certificate[]>("/certificates/");
}

/** Public authenticity check — no session required, only the serial. */
export async function fetchCertificate(serial: string): Promise<Certificate> {
  return api<Certificate>(`/certificates/${encodeURIComponent(serial)}/`);
}
