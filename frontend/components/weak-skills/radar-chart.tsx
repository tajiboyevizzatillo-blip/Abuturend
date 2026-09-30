"use client";

import { cn } from "@/lib/utils";
import type { RadarSubject } from "@/lib/weak-skills";

/**
 * Hand-rolled SVG radar chart.
 *
 * Why no chart library: the project ships no charting dependency, and this is
 * a single polygon with static axes. recharts (~90 kB gzipped) would be added
 * to every route's bundle for one component. The geometry is ~30 lines, has
 * zero runtime deps and stays fully themeable via CSS variables (works in dark
 * mode for free).
 *
 * Accessibility: the polygon is `aria-hidden` and the same numbers are rendered
 * as text next to the chart, so nothing is encoded by shape alone.
 */
export function RadarChart({
  subjects,
  labels,
  size = 260,
  className,
}: {
  subjects: RadarSubject[];
  /** Localized axis labels, same order/length as `subjects`. */
  labels: string[];
  size?: number;
  className?: string;
}) {
  const axes = subjects.length;
  if (axes < 3) {
    // A polygon needs at least 3 axes to read as a radar; below that the
    // caller shows the bar list instead.
    return null;
  }

  const center = size / 2;
  const radius = center - 34;
  const rings = [25, 50, 75, 100];

  const point = (index: number, percent: number) => {
    // Start at 12 o'clock and go clockwise: -90deg in radians.
    const angle = (Math.PI * 2 * index) / axes - Math.PI / 2;
    const r = (radius * Math.max(0, Math.min(100, percent))) / 100;
    return [center + r * Math.cos(angle), center + r * Math.sin(angle)] as const;
  };

  const polygon = subjects
    .map((subject, index) => point(index, subject.accuracy).join(","))
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className={cn("mx-auto h-auto w-full max-w-[320px]", className)}
      aria-hidden="true"
      focusable="false"
    >
      {/* grid rings */}
      {rings.map((ring) => (
        <polygon
          key={ring}
          points={subjects
            .map((_, index) => point(index, ring).join(","))
            .join(" ")}
          fill="none"
          className="stroke-border"
          strokeWidth="1"
        />
      ))}
      {/* axes */}
      {subjects.map((subject, index) => {
        const [x, y] = point(index, 100);
        return (
          <line
            key={subject.subject_id}
            x1={center}
            y1={center}
            x2={x}
            y2={y}
            className="stroke-border"
            strokeWidth="1"
          />
        );
      })}
      {/* the data polygon */}
      <polygon
        points={polygon}
        className="fill-primary-soft stroke-primary"
        strokeWidth="2"
      />
      {/* value dots */}
      {subjects.map((subject, index) => {
        const [x, y] = point(index, subject.accuracy);
        return (
          <circle
            key={subject.subject_id}
            cx={x}
            cy={y}
            r="3.5"
            className={
              subject.enough_data
                ? "fill-primary stroke-surface"
                : "fill-subtle stroke-surface"
            }
          />
        );
      })}
      {/* axis labels */}
      {subjects.map((subject, index) => {
        const [x, y] = point(index, 118);
        return (
          <text
            key={subject.subject_id}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-muted text-[10px] font-semibold"
          >
            {labels[index]}
          </text>
        );
      })}
    </svg>
  );
}

/**
 * Colour rules for an accuracy percentage: <40 red, 40-70 amber, >70 green.
 * The number is always rendered next to the bar, colour is never the only cue.
 */
export function accuracyTone(accuracy: number): {
  bar: string;
  badge: string;
} {
  if (accuracy < 40) return { bar: "bg-danger", badge: "badge-danger" };
  if (accuracy < 70) return { bar: "bg-warning", badge: "badge-warning" };
  return { bar: "bg-success", badge: "badge-success" };
}
