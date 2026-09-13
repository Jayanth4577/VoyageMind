"use client";

import { use } from "react";
import ContingencyTree from "@/components/ContingencyTree/ContingencyTree";

export default function TripContingenciesPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-4xl p-5 md:p-8">
      <ContingencyTree tripId={tripId} />
    </main>
  );
}
