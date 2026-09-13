"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import ItineraryBuilder from "@/components/ItineraryBuilder/ItineraryBuilder";

export default function TripItineraryPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  const router = useRouter();
  return (
    <main className="mx-auto max-w-6xl p-5 md:p-8">
      <ItineraryBuilder
        tripId={tripId}
        onAskAi={(dayNumbers) => {
          const dayText =
            dayNumbers.length === 1 ? `Day ${dayNumbers[0]}` : `days ${dayNumbers.join(", ")}`;
          router.push(
            `/trips/${tripId}/copilot?prompt=${encodeURIComponent(
              `Schedule conflicts were detected on ${dayText}. Propose a realistic reschedule (times and travel time between places) as a suggestion I can accept.`,
            )}`,
          );
        }}
      />
    </main>
  );
}
