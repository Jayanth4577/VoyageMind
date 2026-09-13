"use client";

import { use } from "react";
import WeatherPanel from "@/components/WeatherPanel/WeatherPanel";

export default function TripWeatherPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-5xl p-5 md:p-8">
      <WeatherPanel tripId={tripId} />
    </main>
  );
}
