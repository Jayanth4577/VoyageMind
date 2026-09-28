"use client";

import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "@/services/api";
import { tripsApi } from "@/services/trips";
import type { ItineraryDay, Trip } from "@/types";

// Leaflet needs explicit icon URLs (no bundler asset resolution by default).
const pinIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

const homeIcon = L.divIcon({
  html: '<div style="font-size:22px;line-height:1;filter:drop-shadow(0 1px 2px rgba(0,0,0,.4))">📍</div>',
  className: "",
  iconSize: [24, 24],
  iconAnchor: [12, 22],
  popupAnchor: [0, -20],
});

const DAY_COLORS = ["#059669", "#0d9488", "#65a30d", "#d97706", "#0891b2", "#db2777"];

export default function TripMap({ tripId }: { tripId: string }) {
  const [days, setDays] = useState<ItineraryDay[]>([]);
  const [destination, setDestination] = useState<
    { latitude: number; longitude: number; name: string } | null
  >(null);
  const [unresolved, setUnresolved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [trip, itinerary] = await Promise.all([
          tripsApi.get(tripId),
          tripsApi.itinerary(tripId),
        ]);
        if (!active) return;
        setDays(itinerary.days);

        const t: Trip = trip;
        if (t.destination_lat !== null && t.destination_lng !== null) {
          setDestination({
            latitude: t.destination_lat,
            longitude: t.destination_lng,
            name: t.destination_name,
          });
          return;
        }
        // Resolve (and persist) destination coordinates via the geocode endpoint.
        try {
          const geo = await api.get<{
            latitude: number;
            longitude: number;
            destination_name: string;
          }>(`/trips/${tripId}/geocode`);
          if (active && geo.latitude != null) {
            setDestination({
              latitude: geo.latitude,
              longitude: geo.longitude,
              name: geo.destination_name,
            });
          }
        } catch {
          if (active) setUnresolved(true);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load map");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  const points = useMemo(
    () =>
      days.flatMap((day, di) =>
        day.activities
          .filter((a) => a.latitude !== null && a.longitude !== null)
          .map((a) => ({
            ...a,
            dayNumber: day.day_number,
            color: DAY_COLORS[di % DAY_COLORS.length],
          })),
      ),
    [days],
  );

  const center: [number, number] | null = points.length
    ? [points[0].latitude!, points[0].longitude!]
    : destination
      ? [destination.latitude, destination.longitude]
      : null;

  if (error) return <p className="rounded-lg bg-dangersoft p-3 text-sm text-danger">{error}</p>;

  return (
    <div className="space-y-2 rounded-2xl border border-line bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Map</h2>
        <p className="text-xs text-inksoft/80">
          {points.length > 0
            ? `${points.length} pinned ${points.length === 1 ? "activity" : "activities"}`
            : destination
              ? `Showing ${destination.name} — add activities with locations to pin them`
              : unresolved
                ? "Destination could not be geocoded yet"
                : "Locating destination…"}
        </p>
      </div>

      {center === null ? (
        <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-line px-6 text-center text-sm text-inksoft">
          {unresolved
            ? "We couldn't locate this trip's destination on the map yet — check the destination name, or add activities with coordinates."
            : "Loading map…"}
        </div>
      ) : (
        <MapContainer
          center={center}
          zoom={points.length ? 11 : 12}
          scrollWheelZoom
          className="w-full rounded-lg"
          style={{ height: "22rem" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {destination && (
            <Marker position={[destination.latitude, destination.longitude]} icon={homeIcon}>
              <Popup>
                <strong>{destination.name}</strong>
                <br />
                Trip destination
              </Popup>
            </Marker>
          )}
          {points.map((p) => (
            <Marker key={p.id} position={[p.latitude!, p.longitude!]} icon={pinIcon}>
              <Popup>
                <span style={{ color: p.color, fontWeight: 600 }}>Day {p.dayNumber}</span>
                <br />
                {p.name}
                {p.start_time ? ` · ${p.start_time}` : ""}
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      )}

      <div className="flex flex-wrap gap-3 text-xs text-inksoft">
        {days.map((day, i) => (
          <span key={day.id} className="flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: DAY_COLORS[i % DAY_COLORS.length] }}
            />
            Day {day.day_number}
          </span>
        ))}
      </div>
    </div>
  );
}
