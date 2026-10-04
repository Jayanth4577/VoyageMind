"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { tripsApi } from "@/services/trips";
import { osmPlaceUrl } from "@/services/booking";
import type { ConflictIssue } from "@/types";

interface NearbyPlace {
  name: string;
  place_type: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  population: number | null;
  maps_url: string;
}

interface Props {
  tripId: string;
  days: { id: string; day_number: number }[];
}

/** Nearby destinations worth a day trip, with a guided add-to-itinerary flow:
 *  pick day & time -> activity saved -> conflict check -> jump to Risks /
 *  Contingencies if the new activity clashes with the existing plan. */
export default function NearbyPlaces({ tripId, days }: Props) {
  const router = useRouter();
  const [places, setPlaces] = useState<NearbyPlace[] | null>(null);
  const [source, setSource] = useState<{ source?: string; is_mock?: boolean; note?: string } | null>(
    null,
  );
  const [error, setError] = useState("");
  const [adding, setAdding] = useState<NearbyPlace | null>(null);
  const [dayId, setDayId] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [duration, setDuration] = useState(240);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState<{ issues: ConflictIssue[]; name: string } | null>(null);
  const [added, setAdded] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    tripsApi
      .nearbyDestinations(tripId)
      .then((res) => {
        if (!active) return;
        setPlaces(res.results);
        setSource(res);
      })
      .catch((e) => active && setError(e instanceof Error ? e.message : "Failed to load"));
    return () => {
      active = false;
    };
  }, [tripId]);

  function openAdd(place: NearbyPlace) {
    setAdding(place);
    setDayId(days[0]?.id ?? "");
    setConflict(null);
    setAdded(null);
  }

  async function saveActivity(e: React.FormEvent) {
    e.preventDefault();
    if (!adding) return;
    setBusy(true);
    setError("");
    try {
      const created = await tripsApi.addActivity(tripId, {
        day_id: dayId,
        name: adding.name,
        category: "DAY_TRIP",
        location_name: `Day trip from ${adding.distance_km} km away`,
        latitude: adding.latitude,
        longitude: adding.longitude,
        start_time: startTime,
        duration_minutes: duration,
        weather_sensitive: true,
        indoor: false,
      });
      setAdding(null);

      // Conflict check immediately: does the new activity clash with the plan?
      const report = await tripsApi.checkConflicts(tripId);
      const mine = report.issues.filter((i) => i.activity_ids.includes(created.id));
      if (mine.length > 0) {
        setConflict({ issues: mine, name: adding.name });
      } else {
        setAdded(adding.name);
        setConflict(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the place");
    } finally {
      setBusy(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-primary focus:outline-none";

  return (
    <div className="rounded-2xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">🚗 Nearby places worth a trip</h2>
          <p className="text-xs text-inksoft">
            Real towns around your destination — great as half- or full-day trips.
          </p>
        </div>
        {source && (
          <span className="rounded-full bg-surface2 px-2.5 py-0.5 text-[11px] text-inksoft">
            {source.is_mock ? "⚠ Demo data" : `🛰 ${source.source ?? "live"}`}
          </span>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-danger">{error}</p>}

      {/* Post-add conflict / success feedback */}
      {conflict && (
        <div className="mt-3 rounded-xl border border-warn/40 bg-warnsoft p-3.5">
          <p className="text-sm font-medium text-warn">
            ⚠ &ldquo;{conflict.name}&rdquo; clashes with your existing plan on that day:
          </p>
          <ul className="mt-1 space-y-0.5 text-xs text-ink">
            {conflict.issues.map((i, idx) => (
              <li key={idx}>
                {i.severity === "conflict" ? "✕" : "⚠"} {i.message}
              </li>
            ))}
          </ul>
          <div className="mt-2.5 flex flex-wrap gap-2">
            <button
              onClick={() => router.push(`/trips/${tripId}/risks`)}
              className="rounded-lg bg-warn px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
            >
              Open Risks & Simulate
            </button>
            <button
              onClick={() => router.push(`/trips/${tripId}/contingencies`)}
              className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface2"
            >
              View Contingencies
            </button>
            <span className="self-center text-xs text-inksoft">
              The activity was kept — adjust its time or move another one.
            </span>
          </div>
        </div>
      )}
      {added && !conflict && (
        <p className="mt-3 rounded-xl bg-successsoft p-3 text-sm text-success">
          ✓ {added} added to your itinerary — find it in the Itinerary tab.
        </p>
      )}

      {places === null && !error && <p className="mt-3 text-sm text-inksoft">Scanning the map…</p>}
      {places && places.length === 0 && (
        <p className="mt-3 text-sm text-inksoft">
          No nearby towns found — your destination is well off the beaten path.
        </p>
      )}

      {places && places.length > 0 && (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {places.map((p) => (
            <li key={p.name} className="rounded-xl border border-line bg-surface2/60 p-3.5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">{p.name}</p>
                  <p className="text-xs text-inksoft">
                    {p.place_type} · {p.distance_km} km away
                    {p.population ? ` · pop. ${p.population.toLocaleString()}` : ""}
                  </p>
                </div>
              </div>
              <div className="mt-2.5 flex gap-2">
                <button
                  onClick={() => openAdd(p)}
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
                >
                  Add to itinerary
                </button>
                <a
                  href={osmPlaceUrl(p.latitude, p.longitude)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink transition hover:bg-surface2"
                >
                  View place
                </a>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Add-to-itinerary dialog: day & time selection */}
      {adding && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setAdding(null)}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={saveActivity}
            className="w-full max-w-sm space-y-3 rounded-2xl border border-line bg-surface p-5 shadow-xl"
          >
            <h3 className="font-semibold text-ink">Add {adding.name}</h3>
            <p className="text-xs text-inksoft">
              {adding.distance_km} km away · plan it as a half- or full-day trip.
            </p>
            <label className="block text-xs text-inksoft">
              Day
              <select
                className={`${inputCls} mt-1`}
                value={dayId}
                onChange={(e) => setDayId(e.target.value)}
              >
                {days.map((d) => (
                  <option key={d.id} value={d.id} className="text-ink">
                    Day {d.day_number}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-inksoft">
                Start time
                <input
                  type="time"
                  className={`${inputCls} mt-1`}
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                />
              </label>
              <label className="block text-xs text-inksoft">
                Duration (min)
                <input
                  type="number"
                  min={30}
                  max={720}
                  step={30}
                  className={`${inputCls} mt-1`}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                />
              </label>
            </div>
            {days.length === 0 && (
              <p className="text-xs text-danger">This trip has no days to add to.</p>
            )}
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setAdding(null)}
                className="rounded-lg px-3 py-1.5 text-sm text-inksoft hover:bg-surface2"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy || days.length === 0}
                className="rounded-lg bg-primary px-4 py-1.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Checking…" : "Add & check conflicts"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
