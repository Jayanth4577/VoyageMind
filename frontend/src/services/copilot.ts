/** API client for the AI copilot, suggestions, contingencies, what-if, agents, group. */
import { api } from "./api";

export interface SuggestedChange {
  change_type: string;
  target_day?: number | null;
  target_activity_id?: string | null;
  proposed_data: Record<string, unknown>;
  problem?: string;
  reason?: string;
  impact?: string;
  confidence?: number;
}

export interface Suggestion {
  suggestion_id: string;
  changes: SuggestedChange[];
  problem?: string;
  reasoning?: string;
  impact_summary?: string;
}

export interface CopilotMessage {
  id: string;
  trip_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  data: {
    agent?: string;
    status?: string;
    tool_calls_count?: number;
    suggestion_id?: string;
    suggestions?: Suggestion[];
    error?: string;
  };
  created_at: string;
}

export interface Contingency {
  id: string;
  trip_id: string;
  plan_level: string;
  trigger: string;
  condition: string;
  affected_activity_ids: string[];
  fallback_plan: string[];
  budget_impact: number | null;
  time_impact_minutes: number | null;
  confidence: number | null;
  reason: string;
  requires_user_approval: boolean;
  status: string;
}

export interface WhatIfResult {
  scenario: string;
  parameters: Record<string, unknown>;
  impact_chain: string[];
  affected_activities?: string[];
  budget_delta?: number;
  time_delta_minutes?: number;
  contingency_triggered?: string[];
  suggestions?: Suggestion["changes"];
  reasoning?: string;
}

export interface Recommendation {
  id: string;
  trip_id: string;
  name: string;
  category: string;
  estimated_cost: number | null;
  estimated_duration_minutes: number | null;
  rating: number | null;
  reason: string;
  data_source: string;
  confidence: number | null;
  status: string;
}

export interface PreferenceAnalysis {
  trip_id: string;
  travelers: number;
  people: { person_name: string; preferences: Record<string, number> }[];
  interests: Record<
    string,
    { average: number; coverage: number; min: number; max: number; consensus: number }
  >;
  balanced_weights: Record<string, number>;
  conflicts: { interest: string; detail: string }[];
}

export const copilotApi = {
  send: (tripId: string, message: string) =>
    api.post<{ message: CopilotMessage; suggestions: Suggestion[] | null }>(
      `/trips/${tripId}/copilot`,
      { message },
    ),
  history: (tripId: string) =>
    api.get<CopilotMessage[]>(`/trips/${tripId}/copilot/history`),
  suggestionAction: (
    tripId: string,
    suggestionId: string,
    action: "accept" | "reject",
  ) =>
    api.post<{
      status: string;
      applied_changes: number;
      cascade?: Record<string, unknown>;
    }>(`/trips/${tripId}/suggestions/${suggestionId}/action`, { action }),
  contingencies: (tripId: string) =>
    api.get<Contingency[]>(`/trips/${tripId}/contingencies`),
  contingencyAction: (
    tripId: string,
    contingencyId: string,
    action: "accept" | "dismiss" | "activate",
  ) =>
    api.post<Contingency>(
      `/trips/${tripId}/contingencies/${contingencyId}/action`,
      { action },
    ),
  simulate: (tripId: string, scenario: string, parameters: Record<string, unknown>) =>
    api.post<WhatIfResult>(`/trips/${tripId}/simulate`, { scenario, parameters }),
  generate: (tripId: string) =>
    api.post<{ trip_id: string; status: string; reasoning?: string }>(
      `/trips/${tripId}/generate`,
    ),
  recommendations: (tripId: string) =>
    api.get<Recommendation[]>(`/trips/${tripId}/recommendations`),
  groupPreferences: (tripId: string) =>
    api.get<{ id: string; person_name: string; preferences: Record<string, number> }[]>(
      `/trips/${tripId}/preferences`,
    ),
  setGroupPreferences: (
    tripId: string,
    people: { person_name: string; preferences: Record<string, number> }[],
  ) => api.put<{ saved: number }>(`/trips/${tripId}/preferences`, { people }),
  groupAnalysis: (tripId: string) =>
    api.get<PreferenceAnalysis>(`/trips/${tripId}/preferences/analysis`),
};
