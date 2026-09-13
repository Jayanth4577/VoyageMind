"use client";

import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { tripsApi } from "@/services/trips";
import type { ItineraryDay } from "@/types";

// Leaflet needs explicit icon URLs (no bundler asset resolution by default).
const pinIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

const DAY_COLORS = [
  "#2563eb",
  "#16a34a",
  "#d97706",
  "#dc2626",
  "#7c3aed",
  "#0891b2",
  "#db2777",
];

export default function TripMap({ tripId }: { tripId: string }) {
  const [days, setDays] = useState<ItineraryDay[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    tripsApi
      .itinerary(tripId)
      .then((it) => setDays(it.days))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load map"));
  }, [tripId]);

  const points = useMemo(
    () =>
      days.flatMap((day, di) =>
        day.activities
          .filter((a) => a.latitude !== null && a.longitude !== null)
          .map((a) => ({ ...a, dayNumber: day.day_number, color: DAY_COLORS[di % DAY_COLORS.length] })),
      ),
    [days],
  );

  const center: [number, number] = points.length
    ? [points[0].latitude!, points[0].longitude!]
    : [15.2993, 74.124]; // Goa default until geocoding lands (Phase 3)

  if (error) return <p className="rounded-lg bg-dangersoft p-3 text-sm text-danger">{error}</p>;

  return (
    <div className="space-y-2 rounded-xl border border-line bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Map</h2>
        <p className="text-xs text-inksoft/80">
          {points.length > 0
            ? `${points.length} pinned ${points.length === 1 ? "activity" : "activities"}`
            : "No coordinates yet — add activities with locations"}
        </p>
      </div>
      <MapContainer
        center={center}
        zoom={11}
        scrollWheelZoom
        className="h-80 w-full rounded-lg"
        style={{ height: "20rem" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
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
