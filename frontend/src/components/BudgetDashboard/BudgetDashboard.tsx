"use client";

import { useCallback, useEffect, useState } from "react";
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

interface BudgetItem {
  id: string;
  category: string;
  label: string;
  amount: number;
  currency: string;
  source_ref: string;
}

const CATEGORIES = Object.keys(BUDGET_CATEGORY_LABELS);

export default function BudgetDashboard({ tripId }: { tripId: string }) {
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [items, setItems] = useState<BudgetItem[]>([]);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("accommodation");
  const [label, setLabel] = useState("");
  const [amount, setAmount] = useState(0);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, i] = await Promise.all([tripsApi.budget(tripId), tripsApi.budgetItems(tripId)]);
      setSummary(s);
      setItems(i);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load budget");
    }
  }, [tripId]);

  useEffect(() => {
    (async () => {
      await load();
    })();
  }, [load]);

  async function addItem(e: React.FormEvent) {
    e.preventDefault();
    if (amount <= 0) return;
    setAdding(true);
    setError("");
    try {
      await tripsApi.addBudgetItem(tripId, { category, label, amount });
      setLabel("");
      setAmount(0);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add item");
    } finally {
      setAdding(false);
    }
  }

  async function removeItem(item: BudgetItem) {
    setError("");
    try {
      await tripsApi.deleteBudgetItem(item.id);
      await load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete";
      setError(
        msg.includes("activity")
          ? "This line mirrors an activity's cost — edit or delete the activity in the itinerary instead."
          : msg,
      );
    }
  }

  if (error && !summary)
    return <p className="rounded-lg bg-dangersoft p-3 text-sm text-danger">{error}</p>;
  if (!summary) return <p className="text-sm text-inksoft">Loading budget…</p>;

  const maxCategory = Math.max(1, ...Object.values(summary.by_category));

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-ink">💰 Budget</h2>
          <span
            className={`rounded-full px-3 py-1 text-sm font-medium ${STATE_STYLES[summary.state]}`}
          >
            {STATE_LABELS[summary.state]}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-4 text-center">
          <div className="rounded-xl bg-surface2 p-3">
            <p className="text-xs text-inksoft">Total budget</p>
            <p className="mt-0.5 text-lg font-semibold text-ink">
              {summary.total_budget === null
                ? "—"
                : formatMoney(summary.total_budget, summary.currency)}
            </p>
          </div>
          <div className="rounded-xl bg-surface2 p-3">
            <p className="text-xs text-inksoft">Spent</p>
            <p className="mt-0.5 text-lg font-semibold text-ink">
              {formatMoney(summary.spent, summary.currency)}
            </p>
          </div>
          <div className="rounded-xl bg-surface2 p-3">
            <p className="text-xs text-inksoft">Remaining</p>
            <p
              className={`mt-0.5 text-lg font-semibold ${
                summary.remaining !== null && summary.remaining < 0
                  ? "text-danger"
                  : "text-ink"
              }`}
            >
              {summary.remaining === null
                ? "—"
                : formatMoney(summary.remaining, summary.currency)}
            </p>
          </div>
        </div>

        {Object.keys(summary.by_category).length === 0 ? (
          <p className="mt-4 text-sm text-inksoft/80">
            No costs yet — add activities with estimated costs, or a budget line below.
          </p>
        ) : (
          <ul className="mt-4 space-y-2">
            {Object.entries(summary.by_category).map(([cat, amt]) => (
              <li key={cat} className="text-sm">
                <div className="mb-1 flex justify-between text-inksoft">
                  <span>{BUDGET_CATEGORY_LABELS[cat] ?? cat}</span>
                  <span className="font-medium text-ink">
                    {formatMoney(amt, summary.currency)}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded bg-surface2">
                  <div
                    className="h-full rounded bg-primary"
                    style={{ width: `${(amt / maxCategory) * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}

        {summary.state === "over" && summary.remaining !== null && (
          <p className="mt-4 rounded-lg bg-dangersoft p-3 text-sm text-danger">
            Over budget by {formatMoney(Math.abs(summary.remaining), summary.currency)} — trim
            the largest lines below, or ask the Copilot for cheaper alternatives.
          </p>
        )}
      </div>

      {/* Manage budget lines — this is the "manage" side; Analysis is the "visualize" side */}
      <div className="rounded-2xl border border-line bg-surface p-5">
        <h3 className="font-semibold text-ink">Budget lines</h3>
        <p className="mt-0.5 text-xs text-inksoft">
          Manual costs like flights or hotels. Activity costs live in the itinerary and sync
          here automatically (🔗). For per-day breakdowns and biggest expenses, open{" "}
          <span className="font-medium text-primary">Analysis</span>.
        </p>

        {items.length > 0 && (
          <ul className="mt-3 divide-y divide-line">
            {items.map((item) => {
              const fromActivity = item.source_ref.startsWith("activity:");
              return (
                <li key={item.id} className="flex items-center gap-3 py-2 text-sm">
                  <span className="shrink-0 rounded bg-surface2 px-2 py-0.5 text-[11px] text-inksoft">
                    {BUDGET_CATEGORY_LABELS[item.category] ?? item.category}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-ink">
                    {item.label || "(unlabelled)"}
                  </span>
                  {fromActivity && <span title="Linked to an itinerary activity">🔗</span>}
                  <span className="font-mono text-xs text-ink">
                    {formatMoney(item.amount, item.currency)}
                  </span>
                  <button
                    onClick={() => removeItem(item)}
                    disabled={fromActivity}
                    title={
                      fromActivity
                        ? "Linked to an activity — edit the activity instead"
                        : "Delete line"
                    }
                    className={`text-sm ${
                      fromActivity
                        ? "cursor-not-allowed text-line"
                        : "text-inksoft/60 hover:text-danger"
                    }`}
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <form onSubmit={addItem} className="mt-4 flex flex-wrap items-end gap-2">
          <label className="text-xs text-inksoft">
            Category
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="mt-1 block w-40 appearance-none rounded-xl border border-line bg-surface px-3 py-2 pr-8 text-sm text-ink focus:border-primary focus:outline-none"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c} className="text-ink">
                  {BUDGET_CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 flex-1 text-xs text-inksoft">
            Label
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Flights to Goa"
              maxLength={200}
              className="mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-inksoft/70 focus:border-primary focus:outline-none"
            />
          </label>
          <label className="text-xs text-inksoft">
            Amount
            <input
              type="number"
              min={0}
              value={amount || ""}
              onChange={(e) => setAmount(Number(e.target.value))}
              placeholder="0"
              className="mt-1 block w-28 rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-inksoft/70 focus:border-primary focus:outline-none"
            />
          </label>
          <button
            type="submit"
            disabled={adding || amount <= 0}
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {adding ? "Adding…" : "Add line"}
          </button>
        </form>
        {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      </div>
    </div>
  );
}
