"use client";

import { use } from "react";
import TripMap from "@/components/Map/TripMap";

export default function TripMapPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-5xl p-5 md:p-8">
      <TripMap tripId={tripId} />
    </main>
  );
}
