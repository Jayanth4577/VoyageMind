"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import AICopilot from "@/components/AICopilot/AICopilot";
import BudgetDashboard from "@/components/BudgetDashboard/BudgetDashboard";
import ContingencyTree from "@/components/ContingencyTree/ContingencyTree";
import GroupPanel from "@/components/GroupPanel/GroupPanel";
import ItineraryBuilder from "@/components/ItineraryBuilder/ItineraryBuilder";
import RisksPanel from "@/components/RisksPanel/RisksPanel";
import TripMap from "@/components/Map/TripMap";
import WeatherPanel from "@/components/WeatherPanel/WeatherPanel";
import { copilotApi } from "@/services/copilot";
import { getToken } from "@/services/api";
import { tripsApi } from "@/services/trips";
import { formatMoney, type Trip } from "@/types";

type Tab = "itinerary" | "copilot" | "budget" | "weather" | "map" | "risks" | "contingencies" | "group";

const TABS: { id: Tab; label: string }[] = [
  { id: "itinerary", label: "📅 Itinerary" },
  { id: "copilot", label: "🤖 Copilot" },
  { id: "budget", label: "💰 Budget" },
  { id: "weather", label: "🌦 Weather" },
  { id: "map", label: "🗺 Map" },
  { id: "risks", label: "⚠️ Risks & Simulate" },
  { id: "contingencies", label: "🌳 Contingencies" },
  { id: "group", label: "👥 Group" },
];

export default function TripWorkspacePage() {
  const { tripId } = useParams<{ tripId: string }>();
  const router = useRouter();
  const [trip, setTrip] = useState<Trip | null>(null);
  const [tab, setTab] = useState<Tab>("itinerary");
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [itineraryKey, setItineraryKey] = useState(0);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  const loadTrip = useCallback(async () => {
    try {
      setTrip(await tripsApi.get(tripId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load trip");
    }
  }, [tripId]);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    let active = true;
    (async () => {
      try {
        const t = await tripsApi.get(tripId);
        if (active) setTrip(t);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load trip");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId, router, itineraryKey]);

  const refreshItinerary = useCallback(() => {
    setItineraryKey((k) => k + 1);
    void loadTrip();
  }, [loadTrip]);

  async function generatePlan() {
    setGenerating(true);
    setError("");
    try {
      const res = await copilotApi.generate(tripId);
      refreshItinerary();
      if (res.status === "error") setError(res.reasoning || "AI planning failed");
      else setTab("itinerary");
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI planning failed");
    } finally {
      setGenerating(false);
    }
  }

  function askAiToFix(dayNumbers: number[]) {
    const dayText =
      dayNumbers.length === 1 ? `Day ${dayNumbers[0]}` : `days ${dayNumbers.join(", ")}`;
    setPendingPrompt(
      `Schedule conflicts detected on ${dayText}. Propose a realistic reschedule (times and travel time between places) as a suggestion I can accept.`,
    );
    setTab("copilot");
  }

  if (error && !trip)
    return <main className="p-6 text-red-700">{error}</main>;
  if (!trip) return <main className="p-6 text-slate-500">Loading trip…</main>;

  const interests = (trip.preferences.interests as string[] | undefined) ?? [];

  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-5 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link href="/trips" className="text-sm text-slate-500 hover:text-slate-800">
            ← All trips
          </Link>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs uppercase tracking-wide text-slate-500">
              {trip.days.some((d) => d.activities.length > 0)
                ? "Mode A/B · AI + Custom"
                : "Mode B · Build My Own"}
            </span>
            <button
              onClick={generatePlan}
              disabled={generating}
              className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
              title="Mode A: generate a complete AI itinerary"
            >
              {generating ? "🤖 Planning…" : "🤖 AI Plan (Mode A)"}
            </button>
          </div>
        </div>
        <h1 className="text-2xl font-bold text-slate-800">
          {trip.title || trip.destination_name}
        </h1>
        <p className="text-sm text-slate-500">
          {trip.origin_name ? `${trip.origin_name} → ` : ""}
          {trip.destination_name} · {trip.start_date} to {trip.end_date} · {trip.num_travelers}{" "}
          traveler{trip.num_travelers > 1 ? "s" : ""}
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
        {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      </header>

      <nav className="mb-4 flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1 text-sm">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`rounded-md px-3 py-2 font-medium transition ${
              tab === id ? "bg-white text-slate-800 shadow" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "itinerary" && (
        <ItineraryBuilder key={itineraryKey} tripId={trip.id} onAskAi={askAiToFix} />
      )}
      {tab === "copilot" && (
        <AICopilot
          tripId={trip.id}
          pendingPrompt={pendingPrompt}
          onPromptConsumed={() => setPendingPrompt(null)}
          onItineraryChanged={refreshItinerary}
        />
      )}
      {tab === "budget" && <BudgetDashboard tripId={trip.id} />}
      {tab === "weather" && <WeatherPanel tripId={trip.id} />}
      {tab === "map" && <TripMap tripId={trip.id} />}
      {tab === "risks" && <RisksPanel tripId={trip.id} />}
      {tab === "contingencies" && <ContingencyTree tripId={trip.id} />}
      {tab === "group" && <GroupPanel tripId={trip.id} />}
    </main>
  );
}
