"use client";

import { use } from "react";
import BudgetDashboard from "@/components/BudgetDashboard/BudgetDashboard";

export default function TripBudgetPage({
  params,
}: {
  params: Promise<{ tripId: string }>;
}) {
  const { tripId } = use(params);
  return (
    <main className="mx-auto max-w-4xl p-5 md:p-8">
      <BudgetDashboard tripId={tripId} />
    </main>
  );
}
