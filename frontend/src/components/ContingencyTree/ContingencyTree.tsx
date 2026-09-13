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
  proposed: "bg-surface2 text-inksoft",
  accepted: "bg-primarysoft text-primary",
  dismissed: "bg-surface2 text-inksoft/80 line-through",
  activated: "bg-warnsoft text-warn",
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
    <div className="space-y-4 rounded-xl border border-line bg-surface p-5">
      <div>
        <h2 className="text-lg font-semibold text-ink">🌳 Contingency plans</h2>
        <p className="text-xs text-inksoft">
          Structured fallbacks (Plan B/C/D) generated from risks and what-if simulations. Run a
          simulation in the Risks tab to create more.
        </p>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
      {items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-inksoft/80">
          No contingencies yet.
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((c) => (
            <li key={c.id} className="rounded-lg border border-line p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="rounded-md bg-ink px-2 py-0.5 text-xs font-bold text-white">
                    Plan {c.plan_level}
                  </span>
                  <span className="font-medium text-ink">
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
                      className="rounded-md bg-primary px-3 py-1 text-xs font-semibold text-white hover:bg-primary"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => act(c.id, "dismiss")}
                      className="rounded-md border border-line px-3 py-1 text-xs text-inksoft hover:bg-surface2"
                    >
                      Dismiss
                    </button>
                  </div>
                )}
                {c.status === "accepted" && (
                  <button
                    onClick={() => act(c.id, "activate")}
                    className="rounded-md bg-warnsoft0 px-3 py-1 text-xs font-semibold text-white hover:opacity-90"
                  >
                    Activate
                  </button>
                )}
              </div>
              {c.condition && <p className="mt-2 text-xs text-inksoft">If: {c.condition}</p>}
              {c.fallback_plan.length > 0 && (
                <ul className="mt-2 space-y-1 border-l-2 border-line pl-3 text-sm text-ink">
                  {c.fallback_plan.map((step, i) => (
                    <li key={i}>
                      {i === c.fallback_plan.length - 1 ? "└─" : "├─"} {step}
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-inksoft">
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
              {c.reason && <p className="mt-1 text-xs text-inksoft">Why: {c.reason}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
