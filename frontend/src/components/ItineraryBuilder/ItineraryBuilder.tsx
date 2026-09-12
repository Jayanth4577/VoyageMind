"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Timeline from "@/components/Timeline/Timeline";
import AddActivityDialog from "@/components/ItineraryBuilder/AddActivityDialog";
import { tripsApi } from "@/services/trips";
import type { Activity, ConflictIssue, ItineraryDay } from "@/types";

interface Props {
  tripId: string;
}

export default function ItineraryBuilder({ tripId }: Props) {
  const [days, setDays] = useState<ItineraryDay[]>([]);
  const [issues, setIssues] = useState<ConflictIssue[]>([]);
  const [error, setError] = useState("");
  const [addDialogDay, setAddDialogDay] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  // Bumping reloadKey re-runs the loading effect after each mutation.
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [itinerary, report] = await Promise.all([
          tripsApi.itinerary(tripId),
          tripsApi.checkConflicts(tripId),
        ]);
        if (!active) return;
        setDays(itinerary.days);
        setIssues(report.issues);
        setError("");
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load itinerary");
      } finally {
        if (active) setBusy(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId, reloadKey]);

  const handleMove = async (activityId: string, targetDayId: string) => {
    try {
      await tripsApi.moveActivity(activityId, { target_day_id: targetDayId });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Move failed");
    }
  };

  const handleReorder = async (dayId: string, activityIds: string[]) => {
    try {
      await tripsApi.reorderDay(tripId, dayId, activityIds);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reorder failed");
    }
  };

  const handleDelete = async (activityId: string) => {
    try {
      await tripsApi.deleteActivity(activityId);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const handleAdd = async (dayId: string, input: Partial<Activity>) => {
    await tripsApi.addActivity(tripId, {
      day_id: dayId,
      name: input.name ?? "Untitled",
      category: input.category,
      location_name: input.location_name,
      start_time: input.start_time,
      end_time: input.end_time,
      duration_minutes: input.duration_minutes,
      estimated_cost: input.estimated_cost,
      weather_sensitive: input.weather_sensitive,
      indoor: input.indoor,
    });
    setAddDialogDay(null);
    reload();
  };

  const conflictCount = useMemo(
    () => issues.filter((i) => i.severity === "conflict").length,
    [issues],
  );
  const warningCount = useMemo(
    () => issues.filter((i) => i.severity === "warning").length,
    [issues],
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Itinerary Builder</h2>
        <div className="flex items-center gap-3 text-sm">
          {conflictCount > 0 && (
            <span className="rounded-full bg-red-100 px-3 py-1 text-red-700">
              ✕ {conflictCount} conflict{conflictCount > 1 ? "s" : ""}
            </span>
          )}
          {warningCount > 0 && (
            <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-700">
              ⚠ {warningCount} warning{warningCount > 1 ? "s" : ""}
            </span>
          )}
          {conflictCount === 0 && warningCount === 0 && !busy && (
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-700">
              ✓ Schedule looks valid
            </span>
          )}
        </div>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      {issues.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-slate-200 bg-white p-3 text-sm">
          {issues.map((issue, i) => (
            <li
              key={i}
              className={issue.severity === "conflict" ? "text-red-700" : "text-amber-700"}
            >
              {issue.severity === "conflict" ? "✕" : "⚠"} Day {issue.day_number}: {issue.message}
            </li>
          ))}
        </ul>
      )}

      {busy ? (
        <p className="text-sm text-slate-500">Loading itinerary…</p>
      ) : (
        <Timeline
          days={days}
          issues={issues}
          onMoveActivity={handleMove}
          onReorderDay={handleReorder}
          onDeleteActivity={handleDelete}
          onAddActivity={(dayId) => setAddDialogDay(dayId)}
        />
      )}

      {addDialogDay && (
        <AddActivityDialog
          dayId={addDialogDay}
          onClose={() => setAddDialogDay(null)}
          onSubmit={handleAdd}
        />
      )}
    </div>
  );
}
