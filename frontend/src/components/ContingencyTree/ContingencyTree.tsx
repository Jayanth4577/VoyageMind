"use client";

import { useCallback, useEffect, useState } from "react";
import { copilotApi, type Contingency } from "@/services/copilot";

const TRIGGER_ICONS: Record<string, string> = {
  RAIN: "🌧",
  FLIGHT_DELAY: "✈️",
  HOTEL_ISSUE: "🏨",
  BUDGET_OVERRUN: "💰",
  OTHER: "⚠️",
};

const STATUS_STYLES: Record<string, string> = {
  proposed: "bg-slate-100 text-slate-600",
  accepted: "bg-blue-100 text-blue-700",
  dismissed: "bg-slate-100 text-slate-400 line-through",
  activated: "bg-amber-100 text-amber-700",
};

export default function ContingencyTree({ tripId }: { tripId: string }) {
  const [items, setItems] = useState<Contingency[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await copilotApi.contingencies(tripId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load contingencies");
    }
  }, [tripId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const items = await copilotApi.contingencies(tripId);
        if (active) setItems(items);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load contingencies");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  async function act(id: string, action: "accept" | "dismiss" | "activate") {
    try {
      await copilotApi.contingencyAction(tripId, id, action);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  }

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">🌳 Contingency plans</h2>
        <p className="text-xs text-slate-500">
          Structured fallbacks (Plan B/C/D) generated from risks and what-if simulations. Run a
          simulation in the Risks tab to create more.
        </p>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
          No contingencies yet.
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((c) => (
            <li key={c.id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs font-bold text-white">
                    Plan {c.plan_level}
                  </span>
                  <span className="font-medium text-slate-800">
                    {TRIGGER_ICONS[c.trigger] ?? "⚠️"} {c.trigger.replaceAll("_", " ")}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLES[c.status] ?? ""}`}>
                    {c.status}
                  </span>
                </div>
                {c.status === "proposed" && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => act(c.id, "accept")}
                      className="rounded-md bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-700"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => act(c.id, "dismiss")}
                      className="rounded-md border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      Dismiss
                    </button>
                  </div>
                )}
                {c.status === "accepted" && (
                  <button
                    onClick={() => act(c.id, "activate")}
                    className="rounded-md bg-amber-500 px-3 py-1 text-xs font-semibold text-white hover:bg-amber-600"
                  >
                    Activate
                  </button>
                )}
              </div>
              {c.condition && <p className="mt-2 text-xs text-slate-500">If: {c.condition}</p>}
              {c.fallback_plan.length > 0 && (
                <ul className="mt-2 space-y-1 border-l-2 border-slate-200 pl-3 text-sm text-slate-700">
                  {c.fallback_plan.map((step, i) => (
                    <li key={i}>
                      {i === c.fallback_plan.length - 1 ? "└─" : "├─"} {step}
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                {c.budget_impact !== null && c.budget_impact !== undefined && (
                  <span>💰 impact: {c.budget_impact}</span>
                )}
                {c.time_impact_minutes !== null && c.time_impact_minutes !== undefined && (
                  <span>⏱ impact: {c.time_impact_minutes} min</span>
                )}
                {c.confidence !== null && c.confidence !== undefined && (
                  <span>confidence: {Math.round(c.confidence * 100)}%</span>
                )}
                <span>{c.requires_user_approval ? "needs your approval" : "auto"}</span>
              </div>
              {c.reason && <p className="mt-1 text-xs text-slate-500">Why: {c.reason}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
