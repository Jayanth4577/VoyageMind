"use client";

import { useEffect, useState } from "react";
import { copilotApi, type Recommendation, type WhatIfResult } from "@/services/copilot";
import { tripsApi } from "@/services/trips";
import type { ConflictIssue } from "@/types";

const SCENARIOS = [
  { id: "flight_delay", label: "✈️ Flight delay", param: "delay_hours", default: 3 },
  { id: "rain", label: "🌧 Rain", param: "days", default: 1 },
];

export default function RisksPanel({ tripId }: { tripId: string }) {
  const [conflicts, setConflicts] = useState<ConflictIssue[] | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [scenario, setScenario] = useState(SCENARIOS[0].id);
  const [paramValue, setParamValue] = useState<number>(SCENARIOS[0].default as number);
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [report, recs] = await Promise.all([
          tripsApi.checkConflicts(tripId),
          copilotApi.recommendations(tripId),
        ]);
        if (!active) return;
        setConflicts(report.issues);
        setRecommendations(recs.filter((r) => r.status === "suggested"));
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load risks");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  async function simulate() {
    setSimulating(true);
    setError("");
    try {
      const scenarioDef = SCENARIOS.find((s) => s.id === scenario)!;
      const parameters =
        scenario === "rain"
          ? { days: [paramValue] }
          : { [scenarioDef.param]: paramValue };
      setResult(await copilotApi.simulate(tripId, scenario, parameters));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setSimulating(false);
    }
  }

  const hasConflicts = conflicts && conflicts.length > 0;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold text-ink">⚠️ Schedule risks</h2>
        {conflicts === null ? (
          <p className="text-sm text-inksoft">Checking…</p>
        ) : !hasConflicts ? (
          <p className="mt-2 rounded-lg bg-primarysoft p-3 text-sm text-primary">
            ✓ No schedule conflicts detected.
          </p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {conflicts.map((issue, i) => (
              <li
                key={i}
                className={issue.severity === "conflict" ? "text-danger" : "text-warn"}
              >
                {issue.severity === "conflict" ? "✕" : "⚠"} Day {issue.day_number}: {issue.message}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold text-ink">🧪 &ldquo;What if…?&rdquo; simulator</h2>
        <p className="text-xs text-inksoft">
          Runs the scenario against your real itinerary and shows the impact chain.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            className="rounded-md border border-line px-3 py-2 text-sm"
            value={scenario}
            onChange={(e) => {
              setScenario(e.target.value);
              const def = SCENARIOS.find((s) => s.id === e.target.value)!;
              setParamValue(def.default as number);
            }}
          >
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
          <label className="text-xs text-inksoft">
            {scenario === "flight_delay" ? "Delay (hours)" : "Day number"}
            <input
              type="number"
              min={1}
              max={30}
              value={paramValue}
              onChange={(e) => setParamValue(Number(e.target.value))}
              className="ml-2 w-20 rounded-md border border-line px-2 py-1.5 text-sm"
            />
          </label>
          <button
            onClick={simulate}
            disabled={simulating}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary disabled:opacity-50"
          >
            {simulating ? "Simulating…" : "Simulate"}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-danger">{error}</p>}
        {result && (
          <div className="mt-3 rounded-lg border border-line bg-surface2 p-4">
            <ul className="space-y-1 text-sm text-ink">
              {result.impact_chain.map((step, i) => (
                <li key={i}>
                  {i < result.impact_chain.length - 1 ? "↓" : "•"} {step}
                </li>
              ))}
            </ul>
            {result.reasoning && <p className="mt-2 text-xs text-inksoft">{result.reasoning}</p>}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-line bg-surface p-5">
        <h2 className="text-lg font-semibold text-ink">💡 AI recommendations</h2>
        {recommendations.length === 0 ? (
          <p className="mt-2 text-sm text-inksoft/80">
            None yet — ask the Copilot for suggestions (e.g. &ldquo;recommend places near my
            hotel&rdquo;).
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {recommendations.map((rec) => (
              <li key={rec.id} className="rounded-lg border border-line p-3 text-sm">
                <p className="font-medium text-ink">{rec.name}</p>
                <p className="text-xs text-inksoft">
                  {rec.category}
                  {rec.estimated_cost !== null ? ` · ₹${rec.estimated_cost}` : ""}
                  {rec.rating !== null ? ` · ★ ${rec.rating}` : ""}
                  {rec.data_source ? ` · source: ${rec.data_source}` : ""}
                </p>
                {rec.reason && <p className="mt-1 text-inksoft">{rec.reason}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
