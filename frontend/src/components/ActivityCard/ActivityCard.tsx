"use client";

import type { Activity } from "@/types";
import { formatMoney } from "@/types";

const CATEGORY_STYLES: Record<string, string> = {
  BEACH: "bg-accentsoft text-accent border-line",
  RESTAURANT: "bg-warnsoft text-warn border-line",
  CAFE: "bg-warnsoft text-warn border-line",
  MUSEUM: "bg-primarysoft text-primary border-line",
  TRANSPORT: "bg-surface2 text-ink border-line",
  FREE_TIME: "bg-primarysoft text-primary border-line",
};

const CATEGORY_ICONS: Record<string, string> = {
  BEACH: "🏖️",
  RESTAURANT: "🍽️",
  CAFE: "☕",
  MUSEUM: "🏛️",
  TRANSPORT: "🚕",
  FREE_TIME: "☕",
};

interface Props {
  activity: Activity;
  /** Activity ids currently flagged by the conflict checker (conflict severity). */
  conflictIds?: Set<string>;
  warningIds?: Set<string>;
  onDelete?: (id: string) => void;
  draggable?: boolean;
  onDragStart?: (e: React.DragEvent) => void;
  onDragEnd?: () => void;
}

export default function ActivityCard({
  activity,
  conflictIds,
  warningIds,
  onDelete,
  draggable,
  onDragStart,
  onDragEnd,
}: Props) {
  const hasConflict = conflictIds?.has(activity.id);
  const hasWarning = warningIds?.has(activity.id);
  const style = CATEGORY_STYLES[activity.category] ?? "bg-surface border-line";

  return (
    <div
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`group rounded-lg border p-3 shadow-sm transition ${style} ${
        draggable ? "cursor-grab active:cursor-grabbing" : ""
      } ${hasConflict ? "ring-2 ring-red-400" : hasWarning ? "ring-2 ring-amber-300" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-inksoft">
            {activity.start_time && (
              <span className="font-mono font-semibold text-ink">
                {activity.start_time}
                {activity.end_time ? `–${activity.end_time}` : ""}
              </span>
            )}
            <span className="rounded border border-line bg-surface px-1 py-0.5 text-[10px] uppercase tracking-wide">
              {CATEGORY_ICONS[activity.category] ?? "📍"} {activity.category}
            </span>
            {activity.source === "ai" && <span title="AI recommended">🤖</span>}
            {activity.source === "user" && <span title="User selected">👤</span>}
            {activity.weather_sensitive && !activity.indoor && <span title="Weather sensitive">🌦</span>}
            {activity.estimated_cost > 0 && (
              <span title="Estimated cost">💰 {formatMoney(activity.estimated_cost, "INR")}</span>
            )}
            {hasConflict && <span title="Schedule conflict">✕</span>}
            {hasWarning && !hasConflict && <span title="Possible issue">⚠</span>}
          </div>
          <p className="mt-1 truncate text-sm font-medium text-ink">{activity.name}</p>
          {activity.location_name && (
            <p className="truncate text-xs text-inksoft">{activity.location_name}</p>
          )}
        </div>
        {onDelete && (
          <button
            onClick={() => onDelete(activity.id)}
            className="opacity-0 transition group-hover:opacity-100 text-inksoft/80 hover:text-danger"
            title="Delete activity"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
