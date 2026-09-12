"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import ItineraryBuilder from "@/components/ItineraryBuilder/ItineraryBuilder";
import BudgetDashboard from "@/components/BudgetDashboard/BudgetDashboard";
import TripMap from "@/components/Map/TripMap";
import { getToken } from "@/services/api";
import { tripsApi } from "@/services/trips";
import { formatMoney, type Trip } from "@/types";

type Tab = "itinerary" | "budget" | "map";

const TABS: { id: Tab; label: string }[] = [
  { id: "itinerary", label: "📅 Itinerary" },
  { id: "budget", label: "💰 Budget" },
  { id: "map", label: "🗺 Map" },
];

export default function TripWorkspacePage() {
  const { tripId } = useParams<{ tripId: string }>();
  const router = useRouter();
  const [trip, setTrip] = useState<Trip | null>(null);
  const [tab, setTab] = useState<Tab>("itinerary");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    tripsApi
      .get(tripId)
      .then(setTrip)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load trip"));
  }, [tripId, router]);

  if (error) return <main className="p-6 text-red-700">{error}</main>;
  if (!trip) return <main className="p-6 text-slate-500">Loading trip…</main>;

  const interests = (trip.preferences.interests as string[] | undefined) ?? [];

  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-5 space-y-2">
        <div className="flex items-center justify-between">
          <Link href="/trips" className="text-sm text-slate-500 hover:text-slate-800">
            ← All trips
          </Link>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs uppercase tracking-wide text-slate-500">
            Mode B · Build My Own Trip
          </span>
        </div>
        <h1 className="text-2xl font-bold text-slate-800">
          {trip.title || trip.destination_name}
        </h1>
        <p className="text-sm text-slate-500">
          {trip.origin_name ? `${trip.origin_name} → ` : ""}
          {trip.destination_name} · {trip.start_date} to {trip.end_date} ·{" "}
          {trip.num_travelers} traveler{trip.num_travelers > 1 ? "s" : ""}
          {trip.total_budget ? ` · ${formatMoney(trip.total_budget, trip.currency)}` : ""}
        </p>
        {interests.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {interests.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </header>

      <nav className="mb-4 flex gap-1 rounded-lg bg-slate-100 p-1 text-sm">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 rounded-md py-2 font-medium transition ${
              tab === id ? "bg-white text-slate-800 shadow" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "itinerary" && <ItineraryBuilder tripId={trip.id} />}
      {tab === "budget" && <BudgetDashboard tripId={trip.id} />}
      {tab === "map" && <TripMap tripId={trip.id} />}
    </main>
  );
}
