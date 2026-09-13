"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { analyticsApi, type AnalyticsSummary } from "@/services/analytics";
import { getToken } from "@/services/api";
import { formatMoney } from "@/types";

const STATE_STYLES: Record<string, string> = {
  under: "bg-primarysoft text-primary",
  near: "bg-warnsoft text-warn",
  over: "bg-dangersoft text-danger",
  unknown: "bg-surface2 text-inksoft",
};

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-5">
      <p className="text-xs font-medium tracking-wide text-inksoft uppercase">{label}</p>
      <p className="mt-1.5 text-2xl font-bold tracking-tight">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-inksoft">{sub}</p>}
    </div>
  );
}

function daysUntil(dateStr: string): number {
  return Math.ceil(
    (new Date(dateStr + "T00:00:00").getTime() - Date.now()) / (1000 * 60 * 60 * 24),
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [userName, setUserName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    let active = true;
    (async () => {
      try {
        const [summary, me] = await Promise.all([
          analyticsApi.summary(),
          getToken()
            ? fetch(
                (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") + "/auth/me",
                { headers: { Authorization: `Bearer ${getToken()}` } },
              ).then((r) => (r.ok ? r.json() : { display_name: "" }))
            : Promise.resolve({ display_name: "" }),
        ]);
        if (!active) return;
        setData(summary);
        setUserName(me.display_name || "explorer");
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load dashboard");
      }
    })();
    return () => {
      active = false;
    };
  }, [router]);

  const primary = data
    ? (data.totals_by_currency["INR"] ??
      Object.values(data.totals_by_currency)[0] ?? {
        total_budget: 0,
        total_spent: 0,
        by_category: {},
      })
    : null;

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-5 md:p-8">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
          Welcome back{userName ? `, ${userName}` : ""} 🌿
        </h1>
        <p className="mt-1 text-sm text-inksoft">
          {data
            ? `${data.trip_count} trip${data.trip_count === 1 ? "" : "s"} in your workspace`
            : "Loading your workspace…"}
        </p>

        {error && (
          <p className="mt-4 rounded-xl bg-dangersoft p-3 text-sm text-danger">{error}</p>
        )}

        {data && (
          <>
            {/* Stat cards */}
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Trips planned" value={String(data.trip_count)} />
              <StatCard
                label="Total budget"
                value={formatMoney(primary?.total_budget ?? 0, "INR")}
                sub="across all trips"
              />
              <StatCard
                label="Total spent"
                value={formatMoney(primary?.total_spent ?? 0, "INR")}
                sub={
                  primary && primary.total_budget > 0
                    ? `${Math.round((primary.total_spent / primary.total_budget) * 100)}% of budgets`
                    : undefined
                }
              />
              <StatCard
                label="Upcoming trip"
                value={
                  data.upcoming
                    ? daysUntil(data.upcoming.start_date) >= 0
                      ? `${daysUntil(data.upcoming.start_date)} days`
                      : "in progress"
                    : "—"
                }
                sub={data.upcoming ? data.upcoming.destination_name : "plan one below"}
              />
            </div>

            {/* Upcoming trip highlight */}
            {data.upcoming && (
              <Link
                href={`/trips/${data.upcoming.trip_id}`}
                className="mt-4 block rounded-2xl border border-line bg-gradient-to-r from-primarysoft to-accentsoft p-5 transition hover:shadow-md"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold tracking-wide text-primary uppercase">
                      Next up
                    </p>
                    <p className="mt-0.5 text-lg font-bold">
                      {data.upcoming.title} · {data.upcoming.destination_name}
                    </p>
                    <p className="text-sm text-inksoft">
                      {data.upcoming.start_date} → {data.upcoming.end_date} ·{" "}
                      {data.upcoming.num_travelers} travelers ·{" "}
                      {data.upcoming.activity_count} activities planned
                    </p>
                  </div>
                  <span className="text-2xl">🧳</span>
                </div>
              </Link>
            )}

            {/* Per-trip spending */}
            <div className="mt-6 rounded-2xl border border-line bg-surface p-5">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">Spending by trip</h2>
                <Link href="/analytics" className="text-xs font-semibold text-primary hover:underline">
                  Full analytics →
                </Link>
              </div>
              {data.trips.length === 0 ? (
                <div className="mt-3 rounded-xl border border-dashed border-line p-8 text-center">
                  <p className="text-sm text-inksoft">
                    No trips yet — create your first one and the budget engine starts tracking.
                  </p>
                  <Link
                    href="/trips"
                    className="mt-3 inline-block rounded-full bg-primary px-5 py-2 text-xs font-semibold text-white"
                  >
                    + New trip
                  </Link>
                </div>
              ) : (
                <ul className="mt-4 space-y-4">
                  {data.trips.map((t) => {
                    const pct =
                      t.total_budget && t.total_budget > 0
                        ? Math.min(100, Math.round((t.spent / t.total_budget) * 100))
                        : 0;
                    return (
                      <li key={t.trip_id}>
                        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                          <Link href={`/trips/${t.trip_id}`} className="font-medium hover:text-primary">
                            {t.title}{" "}
                            <span className="text-xs text-inksoft">· {t.destination_name}</span>
                          </Link>
                          <div className="flex items-center gap-2">
                            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATE_STYLES[t.state]}`}>
                              {t.state}
                            </span>
                            <span className="font-mono text-xs">
                              {formatMoney(t.spent, t.currency)}
                              {t.total_budget !== null
                                ? ` / ${formatMoney(t.total_budget, t.currency)}`
                                : ""}
                            </span>
                          </div>
                        </div>
                        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface2">
                          <div
                            className={`h-full rounded-full ${
                              t.state === "over"
                                ? "bg-danger"
                                : t.state === "near"
                                  ? "bg-warn"
                                  : "bg-primary"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* What you can do */}
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["📅", "Build an itinerary", "Drag-and-drop timeline with live conflict checks", "/trips"],
                ["🤖", "Ask the copilot", "Proposals you approve — never silent edits", "/trips"],
                ["🌦️", "Watch the weather", "Per-day forecasts and activity risk flags", "/trips"],
                ["🌳", "Prepare fallbacks", "What-if simulations with structured plans", "/trips"],
              ].map(([icon, title, text, href]) => (
                <Link
                  key={title}
                  href={href}
                  className="rounded-2xl border border-line bg-surface p-4 transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  <span className="text-xl">{icon}</span>
                  <p className="mt-2 text-sm font-semibold">{title}</p>
                  <p className="mt-0.5 text-xs text-inksoft">{text}</p>
                </Link>
              ))}
            </div>
          </>
        )}
      </main>
    </AppShell>
  );
}
