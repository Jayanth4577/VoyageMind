"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { copilotApi } from "@/services/copilot";
import { tripsApi, type Trip, type TripInput } from "@/services/trips";

const TRIP_STYLES = ["", "relaxed", "balanced", "packed", "adventure", "cultural", "luxury"];

/** Post-create choice: how do you want to plan this trip? */
function StartChoiceModal({
  trip,
  onDone,
}: {
  trip: Trip;
  onDone: () => void;
}) {
  const router = useRouter();
  const [working, setWorking] = useState<"ai" | null>(null);
  const [note, setNote] = useState("");

  async function generateWithAi() {
    setWorking("ai");
    setNote("");
    try {
      const res = await copilotApi.generate(trip.id);
      if (res.status === "error") {
        setNote("AI planning hit a snag — you can build it manually instead.");
        setWorking(null);
        return;
      }
      onDone();
      router.push(`/trips/${trip.id}`);
    } catch {
      setNote(
        "AI planning is unavailable (no LLM key configured?). Try 'Build it myself'.",
      );
      setWorking(null);
    }
  }

  const options = [
    {
      icon: "🤖",
      title: "Generate with AI",
      text: "The agent pipeline plans the whole trip — transport, stays, weather-checked days.",
      action: generateWithAi,
      disabled: working !== null,
    },
    {
      icon: "✍️",
      title: "Build it myself",
      text: "Start with an empty timeline and add every stop yourself.",
      action: () => {
        onDone();
        router.push(`/trips/${trip.id}/itinerary`);
      },
      disabled: working !== null,
    },
    {
      icon: "🌿",
      title: "Mixed — AI assists me",
      text: "You build; the copilot suggests activities and fixes as you go.",
      action: () => {
        onDone();
        router.push(
          `/trips/${trip.id}/copilot?prompt=${encodeURIComponent(
            `Help me plan my trip to ${trip.destination_name}. Suggest activities day by day as suggestions I can accept.`,
          )}`,
        );
      },
      disabled: working !== null,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-3xl border border-line bg-surface p-6 shadow-2xl">
        <p className="text-xs font-semibold tracking-wide text-primary uppercase">
          Trip created ✓
        </p>
        <h2 className="mt-1 text-xl font-bold tracking-tight">
          How do you want to plan {trip.title || trip.destination_name}?
        </h2>
        <div className="mt-5 space-y-2.5">
          {options.map((o) => (
            <button
              key={o.title}
              onClick={o.action}
              disabled={o.disabled}
              className="flex w-full items-start gap-3 rounded-2xl border border-line bg-surface2/60 p-4 text-left transition hover:border-primary/50 hover:bg-surface2 disabled:opacity-60"
            >
              <span className="text-xl">{o.icon}</span>
              <span>
                <span className="block text-sm font-semibold">
                  {working === "ai" && o.title === "Generate with AI"
                    ? "Generating… (this can take ~30s)"
                    : o.title}
                </span>
                <span className="mt-0.5 block text-xs text-inksoft">{o.text}</span>
              </span>
            </button>
          ))}
        </div>
        {note && <p className="mt-3 text-sm text-warn">{note}</p>}
        <button
          onClick={() => {
            onDone();
            router.push(`/trips/${trip.id}`);
          }}
          className="mt-4 w-full text-center text-xs font-medium text-inksoft hover:text-ink"
        >
          Skip — just show me the trip overview
        </button>
      </div>
    </div>
  );
}

export default function TripForm({ onCreated }: { onCreated?: () => void }) {
  const [form, setForm] = useState<TripInput>({
    title: "",
    origin_name: "",
    destination_name: "",
    start_date: "",
    end_date: "",
    num_travelers: 2,
    total_budget: 50000,
    currency: "INR",
    trip_style: "",
    constraints: "",
  });
  const [interests, setInterests] = useState<string[]>([]);
  const [interestInput, setInterestInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<Trip | null>(null);

  function set<K extends keyof TripInput>(key: K, value: TripInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function addInterest() {
    const v = interestInput.trim().toLowerCase();
    if (v && !interests.includes(v)) setInterests((list) => [...list, v]);
    setInterestInput("");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!form.destination_name.trim() || !form.start_date || !form.end_date) {
      setError("Destination and both dates are required.");
      return;
    }
    setSaving(true);
    try {
      const trip = await tripsApi.create({
        ...form,
        title: form.title?.trim() || `${form.destination_name} trip`,
        preferences: interests.length ? { interests } : {},
      });
      onCreated?.();
      setCreated(trip); // opens the "how do you want to plan?" modal
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create trip");
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full min-w-0 rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-inksoft/70 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25";
  const selectCls =
    "w-full min-w-0 appearance-none rounded-xl border border-line bg-surface px-3 py-2 pr-8 text-sm text-ink focus:border-primary focus:outline-none";

  return (
    <>
      {created && <StartChoiceModal trip={created} onDone={() => setCreated(null)} />}
      <form
        onSubmit={submit}
        className="space-y-4 rounded-2xl border border-line bg-surface p-5"
      >
        <h2 className="text-lg font-semibold text-ink">Plan a new trip</h2>

        <div className="grid grid-cols-2 gap-3">
          <label className="block text-xs text-inksoft">
            From
            <input
              className={`${inputCls} mt-1`}
              placeholder="Bengaluru"
              value={form.origin_name ?? ""}
              onChange={(e) => set("origin_name", e.target.value)}
            />
          </label>
          <label className="block text-xs text-inksoft">
            To *
            <input
              className={`${inputCls} mt-1`}
              placeholder="Goa"
              value={form.destination_name}
              onChange={(e) => set("destination_name", e.target.value)}
              required
            />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="block text-xs text-inksoft">
            Start date *
            <input
              type="date"
              className={`${inputCls} mt-1`}
              value={form.start_date}
              onChange={(e) => set("start_date", e.target.value)}
              required
            />
          </label>
          <label className="block text-xs text-inksoft">
            End date *
            <input
              type="date"
              className={`${inputCls} mt-1`}
              value={form.end_date}
              min={form.start_date || undefined}
              onChange={(e) => set("end_date", e.target.value)}
              required
            />
          </label>
        </div>

        {/* 2×2 on narrow sidebars, 4-across on wide screens */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <label className="block text-xs text-inksoft">
            Travelers
            <input
              type="number"
              min={1}
              max={30}
              className={`${inputCls} mt-1`}
              value={form.num_travelers ?? 2}
              onChange={(e) => set("num_travelers", Number(e.target.value))}
            />
          </label>
          <label className="block text-xs text-inksoft">
            Budget
            <input
              type="number"
              min={0}
              className={`${inputCls} mt-1`}
              value={form.total_budget ?? 0}
              onChange={(e) => set("total_budget", Number(e.target.value))}
            />
          </label>
          <label className="block text-xs text-inksoft">
            Currency
            <select
              className={`${selectCls} mt-1`}
              value={form.currency ?? "INR"}
              onChange={(e) => set("currency", e.target.value)}
            >
              {["INR", "USD", "EUR", "GBP", "AUD", "SGD"].map((c) => (
                <option key={c} value={c} className="text-ink">
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-inksoft">
            Style
            <select
              className={`${selectCls} mt-1`}
              value={form.trip_style ?? ""}
              onChange={(e) => set("trip_style", e.target.value)}
            >
              {TRIP_STYLES.map((s) => (
                <option key={s} value={s} className="text-ink">
                  {s || "any"}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <p className="text-xs text-inksoft">Interests</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {interests.map((tag) => (
              <button
                type="button"
                key={tag}
                onClick={() => setInterests((list) => list.filter((t) => t !== tag))}
                className="rounded-full bg-primarysoft px-2.5 py-1 text-xs text-primary hover:opacity-80"
              >
                {tag} ✕
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <input
              className={inputCls}
              placeholder="beaches, food, nightlife… (Enter to add)"
              value={interestInput}
              onChange={(e) => setInterestInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addInterest();
                }
              }}
            />
            <button
              type="button"
              onClick={addInterest}
              className="shrink-0 rounded-xl border border-line px-3 text-sm text-inksoft hover:bg-surface2"
            >
              Add
            </button>
          </div>
        </div>

        <label className="block text-xs text-inksoft">
          Constraints
          <textarea
            className={`${inputCls} mt-1`}
            rows={2}
            placeholder="No early mornings, vegetarian food, one rest day…"
            value={form.constraints ?? ""}
            onChange={(e) => set("constraints", e.target.value)}
          />
        </label>

        {error && <p className="text-sm text-danger">{error}</p>}

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded-xl bg-primary py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/25 transition hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Creating…" : "Create trip"}
        </button>
      </form>
    </>
  );
}
