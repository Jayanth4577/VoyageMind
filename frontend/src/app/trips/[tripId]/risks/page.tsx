"use client";

import { use } from "react";
import RisksPanel from "@/components/RisksPanel/RisksPanel";

export default function TripRisksPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-5xl p-5 md:p-8">
      <RisksPanel tripId={tripId} />
    </main>
  );
}
