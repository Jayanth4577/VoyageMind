"use client";

import { use } from "react";
import GroupPanel from "@/components/GroupPanel/GroupPanel";

export default function TripGroupPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-4xl p-5 md:p-8">
      <GroupPanel tripId={tripId} />
    </main>
  );
}
