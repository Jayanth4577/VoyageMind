"use client";

import { use, Suspense } from "react";
import AICopilot from "@/components/AICopilot/AICopilot";

export default function TripCopilotPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-4xl p-5 md:p-8">
      <Suspense fallback={<p className="text-sm text-inksoft">Loading copilot…</p>}>
        <AICopilot tripId={tripId} />
      </Suspense>
    </main>
  );
}
