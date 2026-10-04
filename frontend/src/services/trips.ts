/** Typed wrappers for the backend API (spec §24 surface). */
import { api } from "./api";
import type { BudgetSummary, ConflictReport, ItineraryDay } from "@/types";

export type { BudgetSummary, ConflictReport, ItineraryDay, Trip } from "@/types";
import type { Trip } from "@/types";

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
  budgetItems: (tripId: string) =>
    api.get<
      {
        id: string;
        category: string;
        label: string;
        amount: number;
        currency: string;
        source_ref: string;
      }[]
    >(`/trips/${tripId}/budget/items`),
  addBudgetItem: (
    tripId: string,
    body: { category: string; label?: string; amount: number; currency?: string },
  ) => api.post<{ id: string }>(`/trips/${tripId}/budget`, body),
  deleteBudgetItem: (itemId: string) => api.delete<void>(`/budget-items/${itemId}`),
  checkConflicts: (tripId: string) =>
    api.post<ConflictReport>(`/trips/${tripId}/check-conflicts`),
};

export interface Me {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  trip_count: number;
}

export const authApi = {
  register: (email: string, password: string, displayName: string) =>
    api.post<{ access_token: string }>("/auth/register", {
      email,
      password,
      display_name: displayName,
    }),
  login: (email: string, password: string) =>
    api.post<{ access_token: string }>("/auth/login", { email, password }),
  me: () => api.get<Me>("/auth/me"),
  updateMe: (displayName: string) =>
    api.put<Me>("/auth/me", { display_name: displayName }),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<{ status: string }>("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  forgotPassword: (email: string) =>
    api.post<{
      status: string;
      message: string;
      dev_code?: string;
    }>("/auth/forgot-password", { email }),
  resetPassword: (email: string, code: string, newPassword: string) =>
    api.post<{ status: string }>("/auth/reset-password", {
      email,
      code,
      new_password: newPassword,
    }),
};
