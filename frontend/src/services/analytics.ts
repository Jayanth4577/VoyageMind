/** Analytics API client — deterministic spending aggregates from the backend. */
import { api } from "./api";

export interface TripSpending {
  trip_id: string;
  title: string;
  destination_name: string;
  origin_name: string;
  start_date: string;
  end_date: string;
  status: string;
  num_travelers: number;
  activity_count: number;
  total_budget: number | null;
  spent: number;
  remaining: number | null;
  state: "under" | "near" | "over" | "unknown";
  by_category: Record<string, number>;
  currency: string;
}

export interface AnalyticsSummary {
  trip_count: number;
  trips: TripSpending[];
  totals_by_currency: Record<
    string,
    { total_budget: number; total_spent: number; by_category: Record<string, number>; trips: number }
  >;
  upcoming: TripSpending | null;
}

export const analyticsApi = {
  summary: () => api.get<AnalyticsSummary>("/analytics/summary"),
};
