"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import TripForm from "@/components/TripForm/TripForm";
import { getToken, setToken } from "@/services/api";
import { tripsApi } from "@/services/trips";
import { formatMoney, type Trip } from "@/types";

function tripDates(t: Trip): string {
  const fmt = (d: string) =>
    new Date(d + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const sameYear = t.start_date.slice(0, 4) === t.end_date.slice(0, 4);
  return `${fmt(t.start_date)} – ${sameYear ? "" : t.start_date.slice(0, 4) + " "}${fmt(t.end_date)} ${t.end_date.slice(0, 4)}`;
}

export default function TripsPage() {
  const router = useRouter();
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => setReloadKey((k) => k + 1);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    let active = true;
    tripsApi
      .list()
      .then((res) => {
        if (active) setTrips(res.items);
      })
      .catch((e) => {
        if (!active) return;
        const status = (e as { status?: number }).status;
        if (status === 401) router.push("/login");
        else setError(e instanceof Error ? e.message : "Failed to load trips");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router, reloadKey]);

  async function remove(id: string) {
    if (!window.confirm("Delete this trip and its itinerary?")) return;
    await tripsApi.delete(id);
    reload();
  }

  return (
    <main className="mx-auto max-w-5xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <Link href="/trips" className="text-2xl font-bold text-slate-800">
            🧭 VoyageMind
          </Link>
          <p className="text-sm text-slate-500">Your trips</p>
        </div>
        <button
          onClick={() => {
            setToken(null);
            router.push("/login");
          }}
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          Sign out
        </button>
      </header>

      {error && <p className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      <div className="grid gap-6 md:grid-cols-[1fr_360px]">
        <section className="space-y-3">
          {loading ? (
            <p className="text-sm text-slate-500">Loading trips…</p>
          ) : trips.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-400">
              No trips yet — plan your first one on the right.
            </div>
          ) : (
            trips.map((trip) => (
              <article
                key={trip.id}
                className="group flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <Link href={`/trips/${trip.id}`} className="min-w-0 flex-1">
                  <h2 className="font-semibold text-slate-800 group-hover:text-blue-700">
                    {trip.title || trip.destination_name}
                  </h2>
                  <p className="text-sm text-slate-500">
                    {trip.origin_name ? `${trip.origin_name} → ` : ""}
                    {trip.destination_name} · {tripDates(trip)} · {trip.num_travelers} traveler
                    {trip.num_travelers > 1 ? "s" : ""}
                    {trip.total_budget ? ` · ${formatMoney(trip.total_budget, trip.currency)}` : ""}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {trip.days.length} day{trip.days.length > 1 ? "s" : ""} · status: {trip.status}
                  </p>
                </Link>
                <button
                  onClick={() => remove(trip.id)}
                  className="ml-3 text-slate-300 transition hover:text-red-500"
                  title="Delete trip"
                >
                  🗑
                </button>
              </article>
            ))
          )}
        </section>

        <TripForm />
      </div>
    </main>
  );
}
