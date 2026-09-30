import { api } from "./api";

export interface LeaderboardEntry {
  rank: number;
  display_name: string;
  finished_sessions: number;
  correct_answers: number;
  total_answered: number;
  accuracy_percent: number;
}

/** The public leaderboard (staff excluded). `limit` is clamped server-side to 1..50. */
export function fetchLeaderboard(limit?: number): Promise<LeaderboardEntry[]> {
  const qs = limit ? `?limit=${limit}` : "";
  return api<LeaderboardEntry[]>(`/leaderboard/${qs}`);
}
