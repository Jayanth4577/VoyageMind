"use client";

import { useEffect, useMemo, useState } from "react";
import { tripsApi } from "@/services/trips";
import { BUDGET_CATEGORY_LABELS, formatMoney, type BudgetSummary, type Trip } from "@/types";

const CATEGORY_COLORS = [
  "bg-primarysoft0",
  "bg-teal-500",
  "bg-lime-500",
  "bg-warnsoft0",
  "bg-sky-500",
  "bg-rose-500",
];

interface DaySpend {
  dayNumber: number;
  date: string | null;
  total: number;
  biggest: { name: string; cost: number } | null;
}

export default function TripAnalysis({ tripId }: { tripId: string }) {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [budget, setBudget] = useState<BudgetSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [t, b] = await Promise.all([
          tripsApi.get(tripId),
          tripsApi.budget(tripId),
        ]);
        if (!active) return;
        setTrip(t);
        setBudget(b);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load analysis");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  const daySpends: DaySpend[] = useMemo(() => {
    if (!trip) return [];
    return trip.days.map((d) => {
      const total = d.activities.reduce((n, a) => n + a.estimated_cost, 0);
      const biggest = d.activities.reduce<{ name: string; cost: number } | null>(
        (best, a) => (!best || a.estimated_cost > best.cost ? { name: a.name, cost: a.estimated_cost } : best),
        null,
      );
      return { dayNumber: d.day_number, date: d.date, total, biggest };
    });
  }, [trip]);

  const maxDay = Math.max(1, ...daySpends.map((d) => d.total));
  const totalDays = daySpends.length || 1;
  const avgPerDay = (budget?.spent ?? 0) / totalDays;
  const biggestExpenses = useMemo(() => {
    if (!trip) return [];
    return trip.days
      .flatMap((d) => d.activities.map((a) => ({ name: a.name, cost: a.estimated_cost, day: d.day_number })))
      .filter((a) => a.cost > 0)
      .sort((a, b) => b.cost - a.cost)
      .slice(0, 5);
  }, [trip]);

  if (error) return <p className="rounded-xl bg-dangersoft p-3 text-sm text-danger">{error}</p>;
  if (!trip || !budget) return <p className="text-sm text-inksoft">Loading analysis…</p>;

  const budgetPct =
    budget.total_budget && budget.total_budget > 0
      ? Math.min(100, Math.round((budget.spent / budget.total_budget) * 100))
      : 0;

  return (
    <div className="space-y-4">
      {/* Budget progress */}
      <div className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="font-semibold">Budget progress</h2>
        <div className="mt-3 flex items-end justify-between">
          <p className="text-3xl font-bold tracking-tight">
            {formatMoney(budget.spent, budget.currency)}
          </p>
          <p className="text-sm text-inksoft">
            of {budget.total_budget === null ? "no budget set" : formatMoney(budget.total_budget, budget.currency)}
          </p>
        </div>
        {budget.total_budget !== null && (
          <>
            <div className="mt-3 h-3 overflow-hidden rounded-full bg-surface2">
              <div
                className={`h-full rounded-full ${
                  budget.state === "over"
                    ? "bg-danger"
                    : budget.state === "near"
                      ? "bg-warn"
                      : "bg-gradient-to-r from-primary to-accent"
                }`}
                style={{ width: `${budgetPct}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-inksoft">
              {budgetPct}% of budget used ·{" "}
              <span className={budget.remaining !== null && budget.remaining < 0 ? "text-danger" : "text-primary"}>
                {formatMoney(Math.abs(budget.remaining ?? 0), budget.currency)}{" "}
                {(budget.remaining ?? 0) < 0 ? "over" : "remaining"}
              </span>
            </p>
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Per-day spend */}
        <div className="rounded-2xl border border-line bg-surface p-5">
          <h2 className="font-semibold">Spending per day</h2>
          <p className="text-xs text-inksoft">
            avg {formatMoney(avgPerDay, budget.currency)}/day
          </p>
          <ul className="mt-4 space-y-2.5">
            {daySpends.map((d) => (
              <li key={d.dayNumber} className="flex items-center gap-3">
                <span className="w-12 shrink-0 text-xs font-medium text-inksoft">
                  Day {d.dayNumber}
                </span>
                <div className="h-6 flex-1 overflow-hidden rounded-lg bg-surface2">
                  <div
                    className="flex h-full items-center rounded-lg bg-gradient-to-r from-primary to-accent px-2 text-[10px] font-semibold text-white"
                    style={{ width: `${Math.max(12, (d.total / maxDay) * 100)}%` }}
                  >
                    {d.total > 0 && formatMoney(d.total, budget.currency)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Category split */}
        <div className="rounded-2xl border border-line bg-surface p-5">
          <h2 className="font-semibold">Spending by category</h2>
          <p className="text-xs text-inksoft">includes activity costs & manual lines</p>
          <ul className="mt-4 space-y-3">
            {Object.entries(budget.by_category)
              .sort((a, b) => b[1] - a[1])
              .map(([cat, amount], i) => (
                <li key={cat}>
                  <div className="flex justify-between text-sm">
                    <span className="text-inksoft">{BUDGET_CATEGORY_LABELS[cat] ?? cat}</span>
                    <span className="font-mono font-medium">
                      {formatMoney(amount, budget.currency)}
                    </span>
                  </div>
                  <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-surface2">
                    <div
                      className={`h-full rounded-full ${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}`}
                      style={{
                        width: `${budget.spent > 0 ? (amount / budget.spent) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </li>
              ))}
            {Object.keys(budget.by_category).length === 0 && (
              <li className="text-sm text-inksoft">
                No costs yet — add activities with estimated costs.
              </li>
            )}
          </ul>
        </div>
      </div>

      {/* Biggest expenses */}
      <div className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="font-semibold">Biggest expenses</h2>
        {biggestExpenses.length === 0 ? (
          <p className="mt-2 text-sm text-inksoft">Nothing above ₹0 yet.</p>
        ) : (
          <ol className="mt-3 space-y-2">
            {biggestExpenses.map((e, i) => (
              <li key={i} className="flex items-center gap-3 text-sm">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primarysoft text-xs font-bold text-primary">
                  {i + 1}
                </span>
                <span className="flex-1 truncate">{e.name}</span>
                <span className="text-xs text-inksoft">Day {e.day}</span>
                <span className="font-mono font-medium">
                  {formatMoney(e.cost, budget.currency)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
