"use client";

import Link from "next/link";
import { use } from "react";
import { useEffect, useState } from "react";
import { copilotApi } from "@/services/copilot";
import NearbyPlaces from "@/components/NearbyPlaces/NearbyPlaces";
import { getToken } from "@/services/api";
import { tripsApi } from "@/services/trips";
import { formatMoney, type Trip } from "@/types";

const OPTIONS = [
  { seg: "itinerary", label: "Itinerary Builder", icon: "📅", text: "Drag-and-drop days with live conflict checks" },
  { seg: "copilot", label: "AI Copilot", icon: "🤖", text: "Ask anything; approve every change" },
  { seg: "budget", label: "Budget", icon: "💰", text: "Deterministic totals by category" },
  { seg: "analysis", label: "Spending analysis", icon: "📊", text: "Where the money goes, per day" },
  { seg: "weather", label: "Weather", icon: "🌦️", text: "Forecasts and activity risk flags" },
  { seg: "map", label: "Map", icon: "🗺️", text: "Every pinned stop, color-coded by day" },
  { seg: "risks", label: "Risks & Simulate", icon: "⚠️", text: "Schedule risks and what-if scenarios" },
  { seg: "contingencies", label: "Contingencies", icon: "🌳", text: "Structured fallback plans" },
  { seg: "group", label: "Group preferences", icon: "👥", text: "Balance interests across travelers" },
];

export default function TripOverviewPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);

  const loadTrip = () => {
    tripsApi
      .get(tripId)
      .then((t) => setTrip(t))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  };

  useEffect(() => {
    if (!getToken()) return;
    loadTrip();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripId]);

  async function generatePlan() {
    setGenerating(true);
    setError("");
    try {
      const res = await copilotApi.generate(tripId);
      if (res.status === "error") {
        setError(res.reasoning || "AI planning failed");
        setGenerating(false);
        return;
      }
      loadTrip();
    } catch (e) {
      setError(
        e instanceof Error
          ? `AI planning unavailable: ${e.message}`
          : "AI planning failed",
      );
    } finally {
      setGenerating(false);
    }
  }

  if (error) return <main className="p-8 text-danger">{error}</main>;
  if (!trip) return <main className="p-8 text-inksoft">Loading trip…</main>;

  const activityCount = trip.days.reduce((n, d) => n + d.activities.length, 0);
  const interests = (trip.preferences.interests as string[] | undefined) ?? [];
  const isEmpty = activityCount === 0;

  return (
    <main className="mx-auto max-w-5xl p-5 md:p-8">
      <p className="text-xs font-semibold tracking-wide text-primary uppercase">Trip overview</p>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
          {trip.title || trip.destination_name}
        </h1>
        <div className="flex gap-2">
          <button
            onClick={generatePlan}
            disabled={generating}
            className="rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-primary/25 transition hover:opacity-90 disabled:opacity-50"
            title="Mode A: let the AI plan this trip"
          >
            {generating ? "🤖 Planning… (up to ~30s)" : "🤖 AI Plan this trip"}
          </button>
          <Link
            href={`/trips/${tripId}/itinerary`}
            className="rounded-full border border-line bg-surface px-4 py-2 text-xs font-semibold text-ink transition hover:bg-surface2"
          >
            ✍️ Build manually
          </Link>
        </div>
      </div>
      <p className="mt-1 text-sm text-inksoft">
        {trip.origin_name ? `${trip.origin_name} → ` : ""}
        {trip.destination_name} · {trip.start_date} to {trip.end_date} · {trip.num_travelers}{" "}
        traveler{trip.num_travelers > 1 ? "s" : ""}
        {trip.total_budget
          ? ` · ${formatMoney(trip.total_budget, trip.currency)} budget`
          : ""}
      </p>
      {interests.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {interests.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-primarysoft px-2.5 py-0.5 text-xs font-medium text-primary"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {isEmpty && (
        <div className="mt-6 rounded-2xl border border-dashed border-line bg-surface p-6 text-center">
          <span className="text-2xl">🌱</span>
          <p className="mt-1 text-sm font-medium">This itinerary is empty.</p>
          <p className="mt-0.5 text-xs text-inksoft">
            Let the AI plan it, build it day by day yourself, or mix both — the copilot
            can suggest activities while you build.
          </p>
        </div>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {[
          ["Days", String(trip.days.length)],
          ["Activities", String(activityCount)],
          ["Status", trip.status],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-line bg-surface p-4">
            <p className="text-xs font-medium tracking-wide text-inksoft uppercase">{label}</p>
            <p className="mt-1 text-xl font-bold capitalize">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-6">
        <NearbyPlaces tripId={tripId} days={trip.days.map((d) => ({ id: d.id, day_number: d.day_number }))} />
      </div>

      <h2 className="mt-8 text-lg font-semibold">What can you do in this trip?</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {OPTIONS.map((o) => (
          <Link
            key={o.seg}
            href={`/trips/${tripId}/${o.seg}`}
            className="rounded-2xl border border-line bg-surface p-4 transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
          >
            <span className="text-xl">{o.icon}</span>
            <p className="mt-2 text-sm font-semibold">{o.label}</p>
            <p className="mt-0.5 text-xs text-inksoft">{o.text}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
