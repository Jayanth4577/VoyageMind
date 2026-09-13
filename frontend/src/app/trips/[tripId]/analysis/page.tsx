"use client";

import { use } from "react";
import TripAnalysis from "@/components/Analysis/TripAnalysis";

export default function TripAnalysisPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-5xl p-5 md:p-8">
      <h1 className="text-2xl font-bold tracking-tight">📊 Spending analysis</h1>
      <p className="mt-1 mb-5 text-sm text-inksoft">
        Every number comes from the deterministic budget engine.
      </p>
      <TripAnalysis tripId={tripId} />
    </main>
  );
}
