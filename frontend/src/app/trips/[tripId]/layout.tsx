"use client";

import { use, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { getToken } from "@/services/api";
import { tripsApi } from "@/services/trips";
import type { Trip } from "@/types";

export default function TripLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  const [trip, setTrip] = useState<Trip | null>(null);

  useEffect(() => {
    if (!getToken()) return;
    let active = true;
    tripsApi
      .get(tripId)
      .then((t) => active && setTrip(t))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [tripId]);

  return (
    <AppShell trip={{ id: tripId, name: trip?.title || trip?.destination_name || "Trip" }}>
      {children}
    </AppShell>
  );
}
