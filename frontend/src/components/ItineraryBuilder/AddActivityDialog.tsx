"use client";

import { useState } from "react";
import type { Activity } from "@/types";

const CATEGORIES = [
  "ACTIVITY",
  "BEACH",
  "MUSEUM",
  "RESTAURANT",
  "CAFE",
  "SHOPPING",
  "TRANSPORT",
  "FREE_TIME",
  "NIGHTLIFE",
  "OUTDOOR",
];

interface Props {
  dayId: string;
  onClose: () => void;
  onSubmit: (dayId: string, input: Partial<Activity>) => Promise<void>;
}

export default function AddActivityDialog({ dayId, onClose, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("ACTIVITY");
  const [locationName, setLocationName] = useState("");
  const [startTime, setStartTime] = useState("");
  const [duration, setDuration] = useState(60);
  const [cost, setCost] = useState(0);
  const [weatherSensitive, setWeatherSensitive] = useState(false);
  const [indoor, setIndoor] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError("");
    try {
      await onSubmit(dayId, {
        name: name.trim(),
        category,
        location_name: locationName,
        start_time: startTime,
        duration_minutes: duration,
        estimated_cost: cost,
        weather_sensitive: weatherSensitive,
        indoor,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add activity");
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="w-full max-w-md space-y-3 rounded-xl bg-white p-5 shadow-xl"
      >
        <h3 className="font-semibold text-slate-800">Add activity</h3>

        <input
          autoFocus
          className={inputCls}
          placeholder="Activity name (e.g. Baga Beach)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={200}
        />

        <div className="grid grid-cols-2 gap-3">
          <select className={inputCls} value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          <input
            className={inputCls}
            placeholder="Location (optional)"
            value={locationName}
            onChange={(e) => setLocationName(e.target.value)}
            maxLength={200}
          />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <label className="text-xs text-slate-600">
            Start time
            <input
              type="time"
              className={inputCls}
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
          </label>
          <label className="text-xs text-slate-600">
            Duration (min)
            <input
              type="number"
              min={0}
              max={1440}
              className={inputCls}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </label>
          <label className="text-xs text-slate-600">
            Est. cost (₹)
            <input
              type="number"
              min={0}
              className={inputCls}
              value={cost}
              onChange={(e) => setCost(Number(e.target.value))}
            />
          </label>
        </div>

        <div className="flex gap-4 text-sm text-slate-700">
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={weatherSensitive}
              onChange={(e) => setWeatherSensitive(e.target.checked)}
            />
            🌦 Weather sensitive
          </label>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={indoor} onChange={(e) => setIndoor(e.target.checked)} />
            Indoor
          </label>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !name.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Adding…" : "Add"}
          </button>
        </div>
      </form>
    </div>
  );
}
