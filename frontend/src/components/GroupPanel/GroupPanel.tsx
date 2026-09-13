"use client";

import { useCallback, useEffect, useState } from "react";
import { copilotApi, type PreferenceAnalysis } from "@/services/copilot";

interface PersonRow {
  person_name: string;
  preferences: Record<string, number>;
}

export default function GroupPanel({ tripId }: { tripId: string }) {
  const [people, setPeople] = useState<PersonRow[]>([{ person_name: "", preferences: {} }]);
  const [analysis, setAnalysis] = useState<PreferenceAnalysis | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [rows, a] = await Promise.all([
        copilotApi.groupPreferences(tripId),
        copilotApi.groupAnalysis(tripId),
      ]);
      setPeople(rows.length ? rows : [{ person_name: "", preferences: {} }]);
      setAnalysis(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load preferences");
    }
  }, [tripId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [rows, a] = await Promise.all([
          copilotApi.groupPreferences(tripId),
          copilotApi.groupAnalysis(tripId),
        ]);
        if (!active) return;
        setPeople(rows.length ? rows : [{ person_name: "", preferences: {} }]);
        setAnalysis(a);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load preferences");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  function updatePerson(i: number, patch: Partial<PersonRow>) {
    setPeople((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function updateScore(i: number, interest: string, score: number) {
    setPeople((rows) =>
      rows.map((r, idx) =>
        idx === i ? { ...r, preferences: { ...r.preferences, [interest]: score } } : r,
      ),
    );
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      await copilotApi.setGroupPreferences(
        tripId,
        people
          .filter((p) => Object.keys(p.preferences).length > 0)
          .map((p) => ({ person_name: p.person_name, preferences: p.preferences })),
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const allInterests = Array.from(
    new Set(people.flatMap((p) => Object.keys(p.preferences))),
  );

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-slate-800">👥 Group travel preferences</h2>
        <p className="text-xs text-slate-500">
          Score each traveler&apos;s interests 0–1. The Planner uses the balanced weights when
          generating a plan, and conflicts (spread ≥ 0.5) are flagged.
        </p>

        <div className="mt-4 space-y-4">
          {people.map((person, i) => (
            <div key={i} className="rounded-lg border border-slate-200 p-3">
              <div className="flex items-center gap-2">
                <input
                  className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                  placeholder={`Traveler ${i + 1} name`}
                  value={person.person_name}
                  onChange={(e) => updatePerson(i, { person_name: e.target.value })}
                  maxLength={120}
                />
                {people.length > 1 && (
                  <button
                    onClick={() => setPeople((rows) => rows.filter((_, idx) => idx !== i))}
                    className="text-slate-300 hover:text-red-500"
                    title="Remove traveler"
                  >
                    ✕
                  </button>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-3">
                {allInterests.map((interest) => (
                  <label key={interest} className="text-xs text-slate-600">
                    {interest}
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.1}
                      value={person.preferences[interest] ?? 0.5}
                      onChange={(e) => updateScore(i, interest, Number(e.target.value))}
                      className="ml-2 w-24"
                    />
                    <span className="ml-1 font-mono">
                      {(person.preferences[interest] ?? 0.5).toFixed(1)}
                    </span>
                  </label>
                ))}
                <div className="flex gap-1">
                  <input
                    className="w-28 rounded-md border border-slate-300 px-2 py-1 text-xs"
                    placeholder="add interest…"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const v = (e.target as HTMLInputElement).value.trim().toLowerCase();
                        if (v) {
                          updateScore(i, v, 0.5);
                          (e.target as HTMLInputElement).value = "";
                        }
                      }
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-3 flex gap-2">
          <button
            onClick={() => setPeople((rows) => [...rows, { person_name: "", preferences: {} }])}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            + Add traveler
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save preferences"}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {analysis && analysis.travelers > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-800">
            Balanced plan weights ({analysis.travelers} travelers)
          </h3>
          <ul className="mt-3 space-y-2">
            {Object.entries(analysis.balanced_weights).map(([interest, weight]) => (
              <li key={interest} className="text-sm">
                <div className="flex justify-between text-slate-600">
                  <span className="capitalize">{interest}</span>
                  <span className="font-medium">{Math.round(weight * 100)}%</span>
                </div>
                <div className="mt-0.5 h-2 overflow-hidden rounded bg-slate-100">
                  <div
                    className="h-full rounded bg-blue-500"
                    style={{ width: `${weight * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
          {analysis.conflicts.length > 0 && (
            <div className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-700">
              {analysis.conflicts.map((c) => (
                <p key={c.interest}>
                  ⚠ {c.interest}: {c.detail}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
