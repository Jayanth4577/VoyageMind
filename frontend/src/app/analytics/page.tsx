"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { analyticsApi, type AnalyticsSummary, type TripSpending } from "@/services/analytics";
import { getToken } from "@/services/api";
import { BUDGET_CATEGORY_LABELS, formatMoney } from "@/types";

const CATEGORY_COLORS = [
  "bg-emerald-500",
  "bg-teal-500",
  "bg-lime-500",
  "bg-amber-500",
  "bg-sky-500",
  "bg-rose-500",
];

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    let active = true;
    analyticsApi
      .summary()
      .then((d) => active && setData(d))
      .catch((e) => active && setError(e instanceof Error ? e.message : "Failed to load"));
    return () => {
      active = false;
    };
  }, [router]);

  const totals = data
    ? (data.totals_by_currency["INR"] ??
      Object.values(data.totals_by_currency)[0] ?? {
        total_budget: 0,
        total_spent: 0,
        by_category: {},
      })
    : null;
  const maxCategory = totals
    ? Math.max(1, ...Object.values(totals.by_category))
    : 1;
  const topTrips = data
    ? [...data.trips].sort((a, b) => b.spent - a.spent).slice(0, 5)
    : [];
  const maxTripSpend = topTrips.length ? Math.max(1, ...topTrips.map((t) => t.spent)) : 1;

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-5 md:p-8">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">📊 Spending analytics</h1>
        <p className="mt-1 text-sm text-inksoft">
          Where your money goes, across every trip — computed by the budget engine, never guessed.
        </p>

        {error && <p className="mt-4 rounded-xl bg-dangersoft p-3 text-sm text-danger">{error}</p>}
        {!data && !error && <p className="mt-6 text-sm text-inksoft">Crunching numbers…</p>}

        {data && totals && (
          <>
            {/* Headline numbers */}
            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-line bg-surface p-5">
                <p className="text-xs font-medium tracking-wide text-inksoft uppercase">
                  Total spent
                </p>
                <p className="mt-1 text-2xl font-bold">
                  {formatMoney(totals.total_spent, "INR")}
                </p>
                <p className="text-xs text-inksoft">across {data.trip_count} trips</p>
              </div>
              <div className="rounded-2xl border border-line bg-surface p-5">
                <p className="text-xs font-medium tracking-wide text-inksoft uppercase">
                  Total budgeted
                </p>
                <p className="mt-1 text-2xl font-bold">
                  {formatMoney(totals.total_budget, "INR")}
                </p>
                <p className="text-xs text-inksoft">
                  {totals.total_budget > 0
                    ? `${Math.round((totals.total_spent / totals.total_budget) * 100)}% used`
                    : "no budgets set"}
                </p>
              </div>
              <div className="rounded-2xl border border-line bg-surface p-5">
                <p className="text-xs font-medium tracking-wide text-inksoft uppercase">
                  Avg per trip
                </p>
                <p className="mt-1 text-2xl font-bold">
                  {formatMoney(
                    data.trip_count ? totals.total_spent / data.trip_count : 0,
                    "INR",
                  )}
                </p>
                <p className="text-xs text-inksoft">
                  {totals.trips} trip{totals.trips === 1 ? "" : "s"} in {Object.keys(data.totals_by_currency).join(", ")}
                </p>
              </div>
            </div>

            {data.trip_count === 0 ? (
              <p className="mt-6 rounded-2xl border border-dashed border-line p-10 text-center text-sm text-inksoft">
                No spending yet — plan a trip and add activities with costs.
              </p>
            ) : (
              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                {/* Category breakdown across all trips */}
                <div className="rounded-2xl border border-line bg-surface p-5">
                  <h2 className="font-semibold">Spending by category</h2>
                  <p className="text-xs text-inksoft">all trips combined</p>
                  <ul className="mt-4 space-y-3">
                    {Object.entries(totals.by_category)
                      .sort((a, b) => b[1] - a[1])
                      .map(([cat, amount], i) => (
                        <li key={cat}>
                          <div className="flex justify-between text-sm">
                            <span className="text-inksoft">
                              {BUDGET_CATEGORY_LABELS[cat] ?? cat}
                            </span>
                            <span className="font-mono font-medium">
                              {formatMoney(amount, "INR")}
                            </span>
                          </div>
                          <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-surface2">
                            <div
                              className={`h-full rounded-full ${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}`}
                              style={{ width: `${(amount / maxCategory) * 100}%` }}
                            />
                          </div>
                        </li>
                      ))}
                    {Object.keys(totals.by_category).length === 0 && (
                      <li className="text-sm text-inksoft">No costs recorded yet.</li>
                    )}
                  </ul>
                </div>

                {/* Top trips by spend */}
                <div className="rounded-2xl border border-line bg-surface p-5">
                  <h2 className="font-semibold">Top trips by spend</h2>
                  <p className="text-xs text-inksoft">click a trip to open its analysis</p>
                  <ul className="mt-4 space-y-3">
                    {topTrips.map((t: TripSpending) => (
                      <li key={t.trip_id}>
                        <div className="flex justify-between text-sm">
                          <Link
                            href={`/trips/${t.trip_id}/analysis`}
                            className="font-medium hover:text-primary"
                          >
                            {t.title}
                          </Link>
                          <span className="font-mono font-medium">
                            {formatMoney(t.spent, t.currency)}
                          </span>
                        </div>
                        <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-surface2">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-primary to-accent"
                            style={{ width: `${(t.spent / maxTripSpend) * 100}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Full table */}
            {data.trips.length > 0 && (
              <div className="mt-6 overflow-hidden rounded-2xl border border-line bg-surface">
                <table className="w-full text-left text-sm">
                  <thead className="bg-surface2 text-xs tracking-wide text-inksoft uppercase">
                    <tr>
                      <th className="px-4 py-3">Trip</th>
                      <th className="px-4 py-3">Dates</th>
                      <th className="px-4 py-3 text-right">Budget</th>
                      <th className="px-4 py-3 text-right">Spent</th>
                      <th className="px-4 py-3 text-right">Remaining</th>
                      <th className="px-4 py-3">State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.trips.map((t) => (
                      <tr key={t.trip_id} className="border-t border-line">
                        <td className="px-4 py-3">
                          <Link href={`/trips/${t.trip_id}/analysis`} className="font-medium hover:text-primary">
                            {t.title}
                          </Link>
                          <p className="text-xs text-inksoft">{t.destination_name}</p>
                        </td>
                        <td className="px-4 py-3 text-xs text-inksoft">
                          {t.start_date} → {t.end_date}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs">
                          {t.total_budget === null ? "—" : formatMoney(t.total_budget, t.currency)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs">
                          {formatMoney(t.spent, t.currency)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs">
                          {t.remaining === null ? "—" : formatMoney(t.remaining, t.currency)}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                              t.state === "over"
                                ? "bg-dangersoft text-danger"
                                : t.state === "near"
                                  ? "bg-warnsoft text-warn"
                                  : t.state === "unknown"
                                    ? "bg-surface2 text-inksoft"
                                    : "bg-primarysoft text-primary"
                            }`}
                          >
                            {t.state}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </AppShell>
  );
}
