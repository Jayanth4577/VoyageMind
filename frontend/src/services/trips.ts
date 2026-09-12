/** Typed wrappers for the backend API (spec §24 surface). */
import { api } from "./api";
import type { BudgetSummary, ConflictReport, ItineraryDay, Trip } from "@/types";

export interface TripInput {
  title?: string;
  origin_name?: string;
  destination_name: string;
  start_date: string;
  end_date: string;
  num_travelers?: number;
  total_budget?: number | null;
  currency?: string;
  trip_style?: string;
  constraints?: string;
  preferences?: Record<string, unknown>;
}

export interface ActivityInput {
  day_id: string;
  name: string;
  category?: string;
  location_name?: string;
  latitude?: number | null;
  longitude?: number | null;
  start_time?: string;
  end_time?: string;
  duration_minutes?: number | null;
  estimated_cost?: number;
  weather_sensitive?: boolean;
  indoor?: boolean;
  notes?: string;
}

export const tripsApi = {
  list: () => api.get<{ items: Trip[] }>("/trips"),
  create: (body: TripInput) => api.post<Trip>("/trips", body),
  get: (id: string) => api.get<Trip>(`/trips/${id}`),
  update: (id: string, body: Partial<TripInput> & { status?: string }) =>
    api.put<Trip>(`/trips/${id}`, body),
  delete: (id: string) => api.delete<void>(`/trips/${id}`),

  itinerary: (tripId: string) =>
    api.get<{ trip_id: string; days: ItineraryDay[] }>(`/trips/${tripId}/itinerary`),
  addActivity: (tripId: string, body: ActivityInput) =>
    api.post<ItineraryDay["activities"][number]>(`/trips/${tripId}/activities`, body),
  updateActivity: (activityId: string, body: Partial<ActivityInput>) =>
    api.put<ItineraryDay["activities"][number]>(`/activities/${activityId}`, body),
  deleteActivity: (activityId: string) => api.delete<void>(`/activities/${activityId}`),
  moveActivity: (
    activityId: string,
    body: { target_day_id: string; start_time?: string; end_time?: string },
  ) =>
    api.post<ItineraryDay["activities"][number]>(`/activities/${activityId}/move`, body),
  reorderDay: (tripId: string, dayId: string, activityIds: string[]) =>
    api.post<ItineraryDay>(`/trips/${tripId}/days/${dayId}/reorder`, { activity_ids: activityIds }),

  budget: (tripId: string) => api.get<BudgetSummary>(`/trips/${tripId}/budget`),
  checkConflicts: (tripId: string) =>
    api.post<ConflictReport>(`/trips/${tripId}/check-conflicts`),
};

export const authApi = {
  register: (email: string, password: string, displayName: string) =>
    api.post<{ access_token: string }>("/auth/register", {
      email,
      password,
      display_name: displayName,
    }),
  login: (email: string, password: string) =>
    api.post<{ access_token: string }>("/auth/login", { email, password }),
};
