/** Shared types mirroring the backend Pydantic schemas. */

export interface Activity {
  id: string;
  trip_id: string;
  day_id: string;
  name: string;
  category: string;
  location_name: string;
  latitude: number | null;
  longitude: number | null;
  start_time: string;
  end_time: string;
  duration_minutes: number | null;
  estimated_cost: number;
  weather_sensitive: boolean;
  indoor: boolean;
  source: "user" | "ai" | "api";
  user_selected: boolean;
  ai_recommended: boolean;
  confidence: number | null;
  notes: string;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ItineraryDay {
  id: string;
  trip_id: string;
  day_number: number;
  date: string | null;
  title: string;
  notes: string;
  activities: Activity[];
}

export interface Trip {
  id: string;
  owner_id: string;
  title: string;
  origin_name: string;
  origin_lat: number | null;
  origin_lng: number | null;
  destination_name: string;
  destination_lat: number | null;
  destination_lng: number | null;
  start_date: string;
  end_date: string;
  num_travelers: number;
  total_budget: number | null;
  currency: string;
  trip_style: string;
  constraints: string;
  preferences: Record<string, unknown>;
  status: string;
  days: ItineraryDay[];
}

export interface BudgetSummary {
  trip_id: string;
  currency: string;
  total_budget: number | null;
  spent: number;
  remaining: number | null;
  by_category: Record<string, number>;
  state: "under" | "near" | "over" | "unknown";
}

export interface ConflictIssue {
  kind: string;
  severity: "conflict" | "warning";
  message: string;
  day_number: number;
  activity_ids: string[];
  check: string;
}

export interface ConflictReport {
  trip_id: string;
  issues: ConflictIssue[];
  has_conflicts: boolean;
  has_warnings: boolean;
}

export const BUDGET_CATEGORY_LABELS: Record<string, string> = {
  transport: "Transport",
  accommodation: "Accommodation",
  food: "Food",
  activities: "Activities",
  local_transport: "Local transport",
  buffer: "Buffer",
};

export function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString()}`;
  }
}
