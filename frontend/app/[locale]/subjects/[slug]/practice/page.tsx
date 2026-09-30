"use client";

import { useParams, useSearchParams } from "next/navigation";
import { PracticePlayer } from "@/components/practice/practice-player";

// Optional ?topic=<slug>&count=<n> — used by the onboarding plan so a plan item
// opens exactly the subject/topic/question count the student committed to.
export default function SubjectPracticePage() {
  const params = useParams();
  const search = useSearchParams();
  const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug ?? "";
  const topic = search.get("topic") ?? undefined;
  const rawCount = Number(search.get("count"));
  const questionCount =
    Number.isInteger(rawCount) && rawCount >= 1 && rawCount <= 30
      ? rawCount
      : undefined;
  return (
    <PracticePlayer slug={slug} topicSlug={topic} questionCount={questionCount} />
  );
}
