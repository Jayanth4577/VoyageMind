"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import TripForm from "@/components/TripForm/TripForm";
import { getToken } from "@/services/api";
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
    <AppShell>
      <main className="mx-auto max-w-6xl p-5 md:p-8">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">🧳 My Trips</h1>
        <p className="mt-1 text-sm text-inksoft">Every journey you&apos;re planning, in one place.</p>

        {error && <p className="mt-4 rounded-xl bg-dangersoft p-3 text-sm text-danger">{error}</p>}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_340px]">
          <section className="space-y-3">
            {loading ? (
              <p className="text-sm text-inksoft">Loading trips…</p>
            ) : trips.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-line p-12 text-center">
                <span className="text-3xl">🌱</span>
                <p className="mt-2 text-sm text-inksoft">
                  No trips yet — plan your first adventure on the right.
                </p>
              </div>
            ) : (
              trips.map((trip) => (
                <article
                  key={trip.id}
                  className="group flex items-center justify-between rounded-2xl border border-line bg-surface p-4 transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                >
                  <Link href={`/trips/${trip.id}`} className="min-w-0 flex-1">
                    <h2 className="font-semibold group-hover:text-primary">
                      {trip.title || trip.destination_name}
                    </h2>
                    <p className="mt-0.5 text-sm text-inksoft">
                      {trip.origin_name ? `${trip.origin_name} → ` : ""}
                      {trip.destination_name} · {tripDates(trip)} · {trip.num_travelers} traveler
                      {trip.num_travelers > 1 ? "s" : ""}
                      {trip.total_budget
                        ? ` · ${formatMoney(trip.total_budget, trip.currency)}`
                        : ""}
                    </p>
                    <p className="mt-1 text-xs text-inksoft/80">
                      {trip.days.length} day{trip.days.length > 1 ? "s" : ""} · status:{" "}
                      {trip.status}
                    </p>
                  </Link>
                  <button
                    onClick={() => remove(trip.id)}
                    className="ml-3 text-line transition hover:text-danger"
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
    </AppShell>
  );
}
