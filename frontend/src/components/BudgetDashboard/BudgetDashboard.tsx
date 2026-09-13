"use client";

import { useEffect, useState } from "react";
import { tripsApi } from "@/services/trips";
import { BUDGET_CATEGORY_LABELS, formatMoney, type BudgetSummary } from "@/types";

const STATE_STYLES: Record<BudgetSummary["state"], string> = {
  under: "bg-primarysoft text-primary",
  near: "bg-warnsoft text-warn",
  over: "bg-dangersoft text-danger",
  unknown: "bg-surface2 text-inksoft",
};

const STATE_LABELS: Record<BudgetSummary["state"], string> = {
  under: "Under budget",
  near: "Near budget",
  over: "Over budget",
  unknown: "No budget set",
};

export default function BudgetDashboard({ tripId }: { tripId: string }) {
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    tripsApi
      .budget(tripId)
      .then(setSummary)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load budget"));
  }, [tripId]);

  if (error) return <p className="rounded-lg bg-dangersoft p-3 text-sm text-danger">{error}</p>;
  if (!summary) return <p className="text-sm text-inksoft">Loading budget…</p>;

  const maxCategory = Math.max(1, ...Object.values(summary.by_category));

  return (
    <div className="space-y-4 rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-ink">Budget</h2>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${STATE_STYLES[summary.state]}`}>
          {STATE_LABELS[summary.state]}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4 text-center">
        <div className="rounded-lg bg-surface2 p-3">
          <p className="text-xs text-inksoft">Total budget</p>
          <p className="text-lg font-semibold text-ink">
            {summary.total_budget === null
              ? "—"
              : formatMoney(summary.total_budget, summary.currency)}
          </p>
        </div>
        <div className="rounded-lg bg-surface2 p-3">
          <p className="text-xs text-inksoft">Spent</p>
          <p className="text-lg font-semibold text-ink">
            {formatMoney(summary.spent, summary.currency)}
          </p>
        </div>
        <div className="rounded-lg bg-surface2 p-3">
          <p className="text-xs text-inksoft">Remaining</p>
          <p
            className={`text-lg font-semibold ${
              summary.remaining !== null && summary.remaining < 0 ? "text-danger" : "text-ink"
            }`}
          >
            {summary.remaining === null ? "—" : formatMoney(summary.remaining, summary.currency)}
          </p>
        </div>
      </div>

      {Object.keys(summary.by_category).length === 0 ? (
        <p className="text-sm text-inksoft/80">
          No costs yet — add activities with estimated costs or manual budget items.
        </p>
      ) : (
        <ul className="space-y-2">
          {Object.entries(summary.by_category).map(([category, amount]) => (
            <li key={category} className="text-sm">
              <div className="mb-1 flex justify-between text-inksoft">
                <span>{BUDGET_CATEGORY_LABELS[category] ?? category}</span>
                <span className="font-medium">{formatMoney(amount, summary.currency)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-surface2">
                <div
                  className="h-full rounded bg-primary"
                  style={{ width: `${(amount / maxCategory) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {summary.state === "over" && summary.remaining !== null && (
        <p className="rounded-lg bg-dangersoft p-3 text-sm text-danger">
          Over budget by {formatMoney(Math.abs(summary.remaining), summary.currency)}. Savings
          suggestions arrive with the Budget Agent (Phase 5).
        </p>
      )}
    </div>
  );
}
