"use client";

import { useState } from "react";
import type { Activity, ConflictIssue, ItineraryDay } from "@/types";
import ActivityCard from "@/components/ActivityCard/ActivityCard";

interface Props {
  days: ItineraryDay[];
  issues: ConflictIssue[];
  onMoveActivity: (activityId: string, targetDayId: string) => void;
  onReorderDay: (dayId: string, activityIds: string[]) => void;
  onDeleteActivity: (activityId: string) => void;
  onAddActivity: (dayId: string) => void;
}

/** Drag payload travels as JSON in the native dataTransfer. */
interface DragPayload {
  activityId: string;
  sourceDayId: string;
}

function dayIdsWithSeverity(issues: ConflictIssue[], severity: string): Set<string> {
  return new Set(issues.filter((i) => i.severity === severity).flatMap((i) => i.activity_ids));
}

function sortForDrop(target: Activity[], draggedId: string, beforeId: string | null): string[] {
  const ids = target.map((a) => a.id).filter((id) => id !== draggedId);
  if (beforeId === null) {
    ids.push(draggedId);
  } else {
    const idx = ids.indexOf(beforeId);
    if (idx === -1) ids.push(draggedId);
    else ids.splice(idx, 0, draggedId);
  }
  return ids;
}

export default function Timeline({
  days,
  issues,
  onMoveActivity,
  onReorderDay,
  onDeleteActivity,
  onAddActivity,
}: Props) {
  const [dragging, setDragging] = useState<DragPayload | null>(null);
  const [dropTarget, setDropTarget] = useState<{ dayId: string; beforeId: string | null } | null>(
    null,
  );

  const conflictIds = dayIdsWithSeverity(issues, "conflict");
  const warningIds = dayIdsWithSeverity(issues, "warning");

  function handleDrop(day: ItineraryDay) {
    const target = dropTarget;
    setDropTarget(null);
    if (!dragging) return;
    const { activityId, sourceDayId } = dragging;
    setDragging(null);

    if (day.id === sourceDayId) {
      // Reorder within the same day at the requested position
      const ids = sortForDrop(day.activities, activityId, target?.dayId === day.id ? target.beforeId : null);
      if (ids.join(",") !== day.activities.map((a) => a.id).join(",")) {
        onReorderDay(day.id, ids);
      }
    } else {
      onMoveActivity(activityId, day.id);
    }
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {days.map((day) => {
        const dayIssues = issues.filter((i) => i.day_number === day.day_number);
        const hasConflict = dayIssues.some((i) => i.severity === "conflict");
        const isDropRow =
          dropTarget?.dayId === day.id &&
          (dropTarget.beforeId === null || dropTarget.beforeId === day.activities[0]?.id);
        return (
          <section
            key={day.id}
            onDragOver={(e) => {
              e.preventDefault();
              if (dropTarget?.dayId !== day.id || dropTarget.beforeId !== null) {
                setDropTarget({ dayId: day.id, beforeId: null });
              }
            }}
            onDrop={() => handleDrop(day)}
            className={`flex w-72 shrink-0 flex-col rounded-xl border p-3 ${
              dropTarget?.dayId === day.id
                ? "border-primary bg-primarysoft"
                : "border-line bg-surface2"
            }`}
          >
            <header className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-ink">
                  Day {day.day_number} {hasConflict && <span title="Conflicts found">✕</span>}
                  {!hasConflict && dayIssues.length > 0 && <span title="Warnings">⚠</span>}
                </h3>
                {day.date && (
                  <p className="text-xs text-inksoft">
                    {new Date(day.date + "T00:00:00").toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                )}
              </div>
              <button
                onClick={() => onAddActivity(day.id)}
                className="rounded-md bg-primary px-2 py-1 text-xs font-medium text-white hover:bg-primary"
              >
                + Add
              </button>
            </header>

            <div className="flex flex-1 flex-col gap-2">
              {isDropRow && dragging && (
                <div className="h-1.5 rounded bg-primary" aria-hidden />
              )}
              {day.activities.length === 0 && (
                <p className="rounded-lg border border-dashed border-line p-4 text-center text-xs text-inksoft/80">
                  Drop activities here
                </p>
              )}
              {day.activities.map((activity, i) => {
                const isBefore =
                  dropTarget?.dayId === day.id && dropTarget.beforeId === activity.id;
                return (
                  <div key={activity.id}>
                    {isBefore && dragging && <div className="mb-2 h-1.5 rounded bg-primary" aria-hidden />}
                    <ActivityCard
                      activity={activity}
                      conflictIds={conflictIds}
                      warningIds={warningIds}
                      onDelete={onDeleteActivity}
                      draggable
                      onDragStart={(e) => {
                        const payload: DragPayload = {
                          activityId: activity.id,
                          sourceDayId: day.id,
                        };
                        e.dataTransfer.setData("text/plain", JSON.stringify(payload));
                        e.dataTransfer.effectAllowed = "move";
                        setDragging(payload);
                      }}
                      onDragEnd={() => {
                        setDragging(null);
                        setDropTarget(null);
                      }}
                    />
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const nextId = day.activities[i + 1]?.id ?? null;
                        if (dropTarget?.dayId !== day.id || dropTarget.beforeId !== nextId) {
                          setDropTarget({ dayId: day.id, beforeId: nextId });
                        }
                      }}
                      className="h-2"
                      aria-hidden
                    />
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
