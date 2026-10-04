"use client";

import { use } from "react";
import { useEffect, useState } from "react";
import { bookingComUrl, goibiboStaysUrl, googleFlightsUrl, irctcTrainsUrl, redbusUrl } from "@/services/booking";
import { tripsApi } from "@/services/trips";
import { formatMoney } from "@/types";

type Transport = Awaited<ReturnType<typeof tripsApi.transportOptions>>;
type Stays = Awaited<ReturnType<typeof tripsApi.stayOptions>>;

function DemoBanner({ note }: { note?: string }) {
  return (
    <p className="rounded-xl bg-warnsoft p-3 text-sm text-warn">
      {note ?? "Demo options — connect a provider key for live prices."}
    </p>
  );
}

function SourceBadge({ data }: { data: { source?: string; is_mock?: boolean; cached?: boolean } }) {
  return (
    <span className="rounded-full bg-surface2 px-2.5 py-0.5 text-[11px] text-inksoft">
      {data.is_mock ? "⚠ Demo data" : `🛰 ${data.source ?? "live"}`}
      {data.cached ? " · cached" : ""}
    </span>
  );
}

export default function TripTransportPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  const [transport, setTransport] = useState<Transport | null>(null);
  const [stays, setStays] = useState<Stays | null>(null);
  const [trip, setTrip] = useState<{
    origin_name: string;
    destination_name: string;
    start_date: string;
    end_date: string;
    num_travelers: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [transportError, setTransportError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const t = await tripsApi.get(tripId);
        if (!active) return;
        setTrip({
          origin_name: t.origin_name,
          destination_name: t.destination_name,
          start_date: t.start_date,
          end_date: t.end_date,
          num_travelers: t.num_travelers,
        });
        const [tr, st] = await Promise.all([
          tripsApi.transportOptions(tripId).catch((e) => {
            if (active) setTransportError(e instanceof Error ? e.message : "unavailable");
            return null;
          }),
          tripsApi.stayOptions(tripId),
        ]);
        if (!active) return;
        if (tr) setTransport(tr);
        setStays(st);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  if (error) return <main className="p-8 text-danger">{error}</main>;

  const q = transport?.query ?? trip
    ? {
        origin: transport?.query.origin ?? trip?.origin_name ?? "",
        destination: transport?.query.destination ?? trip?.destination_name ?? "",
        date: transport?.query.date ?? trip?.start_date ?? "",
      }
    : null;

  return (
    <main className="mx-auto max-w-5xl p-5 md:p-8">
      <h1 className="font-display text-2xl font-bold tracking-tight md:text-3xl">
        🚕 Travel & Stays
      </h1>
      <p className="mt-1 text-sm text-inksoft">
        Compare options, then book on the provider&apos;s own site — we hand you off
        pre-filled, free, and never take a payment.
      </p>

      {q && (
        <div className="mt-4 flex flex-wrap gap-2 text-sm">
          <a
            href={googleFlightsUrl(q.origin, q.destination, q.date)}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-line bg-surface px-3.5 py-1.5 font-medium text-ink transition hover:bg-surface2"
          >
            ✈️ Flights on Google Flights
          </a>
          <a
            href={irctcTrainsUrl(q.origin, q.destination)}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-line bg-surface px-3.5 py-1.5 font-medium text-ink transition hover:bg-surface2"
          >
            🚆 Trains on IRCTC
          </a>
          <a
            href={redbusUrl(q.origin, q.destination, q.date)}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-line bg-surface px-3.5 py-1.5 font-medium text-ink transition hover:bg-surface2"
          >
            🚌 Buses on RedBus
          </a>
          {stays && !stays.is_mock && (
            <a
              href={bookingComUrl(q.destination, trip?.start_date ?? "", trip?.end_date ?? "", trip?.num_travelers ?? 2)}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full border border-line bg-surface px-3.5 py-1.5 font-medium text-ink transition hover:bg-surface2"
            >
              🏨 Hotels on Booking.com
            </a>
          )}
        </div>
      )}

      {/* Transport options */}
      <section className="mt-6 rounded-2xl border border-line bg-surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">✈️ Transport options</h2>
          {transport && <SourceBadge data={transport} />}
        </div>
        {transportError && (
          <p className="mt-3 text-sm text-warn">{transportError}</p>
        )}
        {!transport && !transportError && (
          <p className="mt-3 text-sm text-inksoft">Loading options…</p>
        )}
        {transport?.note && !transport.is_mock && (
          <p className="mt-3 rounded-xl bg-accentsoft p-3 text-sm text-ink">{transport.note}</p>
        )}
        {transport?.is_mock && transport.note && (
          <div className="mt-3">
            <DemoBanner note={transport.note} />
          </div>
        )}

        {/* Multimodal route suggestions (no-airport destinations) */}
        {transport && (transport.route_options?.length ?? 0) > 0 && (
          <div className="mt-4 space-y-2.5">
            <p className="text-xs font-semibold tracking-wide text-inksoft uppercase">
              Suggested ways to get there
            </p>
            {transport.route_options!.map((route) => {
              const modeIcon =
                route.mode === "flight_road" ? "✈️🚌" : route.mode === "train" ? "🚆" : "🚌";
              const linkLabel =
                route.mode === "flight_road"
                  ? "Book flight"
                  : route.mode === "train"
                    ? "Check trains on IRCTC"
                    : "Book bus on RedBus";
              const link =
                route.links.flight ?? route.links.train ?? route.links.bus ?? "#";
              return (
                <div
                  key={route.mode + route.title}
                  className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface2/60 p-3.5"
                >
                  <span className="text-lg">{modeIcon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink">{route.title}</p>
                    {route.mode === "flight_road" && route.flight_price ? (
                      <p className="text-xs text-inksoft">
                        from{" "}
                        <span className="font-mono font-semibold text-primary">
                          {formatMoney(route.flight_price, route.currency ?? "INR")}
                        </span>{" "}
                        + road leg
                      </p>
                    ) : (
                      <p className="text-xs text-inksoft">
                        {route.mode === "train"
                          ? "fares vary — check IRCTC for your dates"
                          : "often the cheapest option for these routes"}
                      </p>
                    )}
                  </div>
                  <a
                    href={link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
                  >
                    {linkLabel}
                  </a>
                </div>
              );
            })}
            <p className="text-xs text-inksoft/70">
              Flight prices are live. Bus/train fares aren&apos;t available via free APIs — the
              buttons open the official bookers with your route pre-filled.
            </p>
          </div>
        )}
        {transport && transport.offers.length === 0 && (
          <p className="mt-3 text-sm text-inksoft">
            No options returned — try the booking links above directly.
          </p>
        )}
        {transport && transport.offers.length > 0 && (
          <ul className="mt-3 divide-y divide-line">
            {transport.offers.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                <span className="min-w-0 flex-1">
                  <span className="font-medium text-ink">{o.airline ?? "Transport"}</span>
                  <span className="block text-xs text-inksoft">
                    {o.departure_at} → {o.arrival_at}
                    {o.duration_minutes ? ` · ${Math.round(o.duration_minutes / 60)}h ${o.duration_minutes % 60}m` : ""}
                  </span>
                </span>
                {o.price !== null && o.price > 0 && (
                  <span className="font-mono text-sm text-ink">
                    {formatMoney(o.price, o.currency)}
                  </span>
                )}
                <a
                  href={googleFlightsUrl(
                    transport.query.origin,
                    transport.query.destination,
                    transport.query.date,
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
                >
                  Book ticket
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Stays */}
      <section className="mt-4 rounded-2xl border border-line bg-surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">🏨 Stays</h2>
          {stays && <SourceBadge data={stays} />}
        </div>
        {stays?.is_mock && stays.note && (
          <div className="mt-3">
            <DemoBanner note={stays.note} />
          </div>
        )}
        {stays && stays.stays.length > 0 && (
          <ul className="mt-3 divide-y divide-line">
            {stays.stays.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                <span className="min-w-0 flex-1">
                  <span className="font-medium text-ink">{s.name}</span>
                  <span className="block text-xs text-inksoft">
                    {s.location_name}
                    {s.rating ? ` · ★ ${s.rating}` : ""}
                  </span>
                </span>
                {s.price_per_night !== null && (
                  <span className="font-mono text-sm text-ink">
                    {formatMoney(s.price_per_night, "INR")}
                    <span className="text-xs text-inksoft"> / night</span>
                  </span>
                )}
                {trip && (
                  <a
                    href={bookingComUrl(
                      trip.destination_name,
                      trip.start_date,
                      trip.end_date,
                      trip.num_travelers,
                    )}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
                  >
                    Book stay
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
        {stays && stays.stays.length === 0 && (
          <p className="mt-3 text-sm text-inksoft">
            No stays returned — use the hotel links above to browse live options.
          </p>
        )}
        {trip && (
          <div className="mt-3 flex flex-wrap gap-2">
            <a
              href={bookingComUrl(trip.destination_name, trip.start_date, trip.end_date, trip.num_travelers)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-medium text-primary hover:underline"
            >
              All hotels on Booking.com →
            </a>
            <a
              href={goibiboStaysUrl(trip.destination_name, trip.start_date, trip.end_date)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-medium text-primary hover:underline"
            >
              GoIbibo →
            </a>
          </div>
        )}
      </section>
    </main>
  );
}
