"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";

interface WeatherDay {
  date?: string;
  temp_max_c?: number | null;
  temp_min_c?: number | null;
  precipitation_mm?: number | null;
  rain_probability?: number | null;
  weather_code?: number | null;
  significant_rain?: boolean;
}

interface WeatherResponse {
  source?: string;
  retrieved_at?: string;
  is_mock?: boolean;
  cached?: boolean;
  note?: string;
  current?: { temperature_c?: number | null; weather_code?: number | null };
  daily: WeatherDay[];
  resolved_destination?: { latitude: number; longitude: number };
}

interface WeatherRiskDay {
  day_number: number;
  date: string | null;
  risk: string;
  reasons: string[];
  affected_activity_ids: string[];
  suggestion: string;
}

interface WeatherRiskReport {
  status: string;
  source?: string;
  is_mock?: boolean;
  days: WeatherRiskDay[];
  days_at_risk: number;
}

const RISK_STYLES: Record<string, string> = {
  none: "bg-emerald-100 text-emerald-700",
  rain: "bg-sky-100 text-sky-700",
  heat: "bg-orange-100 text-orange-700",
  severe: "bg-red-100 text-red-700",
};

function SourceBadge({ data }: { data: { source?: string; retrieved_at?: string; is_mock?: boolean; cached?: boolean } }) {
  const label = data.is_mock ? "Demo data" : data.source || "Unknown source";
  const time = data.retrieved_at
    ? new Date(data.retrieved_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : null;
  return (
    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] text-slate-500">
      {data.is_mock ? "⚠ " : "🛰 "}
      {label}
      {time ? ` · updated ${time}` : ""}
      {data.cached ? " · cached" : ""}
    </span>
  );
}

export default function WeatherPanel({ tripId }: { tripId: string }) {
  const [forecast, setForecast] = useState<WeatherResponse | null>(null);
  const [risks, setRisks] = useState<WeatherRiskReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [wx, riskReport] = await Promise.all([
          api.get<WeatherResponse>(`/trips/${tripId}/weather`),
          api.post<WeatherRiskReport>(`/trips/${tripId}/check-weather`),
        ]);
        if (!active) return;
        setForecast(wx);
        setRisks(riskReport);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Weather unavailable");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  if (error)
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-red-700">
        {error}
      </div>
    );
  if (!forecast || !risks)
    return <p className="text-sm text-slate-500">Loading weather…</p>;

  return (
    <div className="space-y-4">
      {forecast.is_mock && forecast.note && (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-700">{forecast.note}</p>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-800">🌦 Forecast</h2>
          <SourceBadge data={forecast} />
        </div>
        <div className="flex gap-3 overflow-x-auto pb-2">
          {forecast.daily.map((day, i) => (
            <div
              key={i}
              className={`w-40 shrink-0 rounded-lg border p-3 ${
                day.significant_rain ? "border-sky-300 bg-sky-50" : "border-slate-200 bg-slate-50"
              }`}
            >
              <p className="text-xs font-medium text-slate-500">
                {day.date && day.date.includes("-")
                  ? new Date(day.date + "T00:00:00").toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })
                  : day.date || `Day ${i + 1}`}
              </p>
              <p className="mt-1 text-xl font-semibold text-slate-800">
                {day.temp_max_c !== null && day.temp_max_c !== undefined
                  ? `${Math.round(day.temp_max_c)}°C`
                  : "—"}
              </p>
              <p className="text-xs text-slate-500">
                min {day.temp_min_c !== null && day.temp_min_c !== undefined ? `${Math.round(day.temp_min_c)}°` : "—"}
                {day.rain_probability !== null && day.rain_probability !== undefined
                  ? ` · 🌧 ${day.rain_probability}%`
                  : ""}
              </p>
              {day.significant_rain && (
                <p className="mt-1 text-xs font-medium text-sky-700">Significant rain likely</p>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-800">Activity weather risk</h2>
          <SourceBadge data={risks} />
        </div>
        {risks.status !== "ok" && (
          <p className="text-sm text-slate-500">
            Weather risks unavailable for this trip&apos;s destination.
          </p>
        )}
        {risks.status === "ok" && risks.days_at_risk === 0 && (
          <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">
            ✓ No weather risks detected for the current plan.
          </p>
        )}
        <ul className="space-y-2">
          {risks.days
            .filter((d) => d.risk !== "none")
            .map((day) => (
              <li key={day.day_number} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${RISK_STYLES[day.risk]}`}>
                    Day {day.day_number}: {day.risk}
                  </span>
                  <span className="text-xs text-slate-500">{day.reasons.join(" · ")}</span>
                </div>
                {day.suggestion && <p className="mt-1 text-slate-600">{day.suggestion}</p>}
                {day.affected_activity_ids.length > 0 && (
                  <p className="mt-1 text-xs text-slate-500">
                    {day.affected_activity_ids.length} outdoor activity(s) at risk — ask the
                    Copilot to reschedule them.
                  </p>
                )}
              </li>
            ))}
        </ul>
      </div>
    </div>
  );
}
