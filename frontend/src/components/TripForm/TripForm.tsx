"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { tripsApi, type TripInput } from "@/services/trips";

const TRIP_STYLES = ["", "relaxed", "balanced", "packed", "adventure", "cultural", "luxury"];

export default function TripForm({ onCreated }: { onCreated?: () => void }) {
  const router = useRouter();
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
      router.push(`/trips/${trip.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create trip");
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none";

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-slate-800">Plan a new trip</h2>

      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-slate-600">
          From
          <input
            className={inputCls}
            placeholder="Bengaluru"
            value={form.origin_name ?? ""}
            onChange={(e) => set("origin_name", e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          To *
          <input
            className={inputCls}
            placeholder="Goa"
            value={form.destination_name}
            onChange={(e) => set("destination_name", e.target.value)}
            required
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-slate-600">
          Start date *
          <input
            type="date"
            className={inputCls}
            value={form.start_date}
            onChange={(e) => set("start_date", e.target.value)}
            required
          />
        </label>
        <label className="text-xs text-slate-600">
          End date *
          <input
            type="date"
            className={inputCls}
            value={form.end_date}
            min={form.start_date || undefined}
            onChange={(e) => set("end_date", e.target.value)}
            required
          />
        </label>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <label className="text-xs text-slate-600">
          Travelers
          <input
            type="number"
            min={1}
            max={30}
            className={inputCls}
            value={form.num_travelers ?? 2}
            onChange={(e) => set("num_travelers", Number(e.target.value))}
          />
        </label>
        <label className="text-xs text-slate-600">
          Budget
          <input
            type="number"
            min={0}
            className={inputCls}
            value={form.total_budget ?? 0}
            onChange={(e) => set("total_budget", Number(e.target.value))}
          />
        </label>
        <label className="text-xs text-slate-600">
          Currency
          <select
            className={inputCls}
            value={form.currency ?? "INR"}
            onChange={(e) => set("currency", e.target.value)}
          >
            {["INR", "USD", "EUR", "GBP", "AUD", "SGD"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-600">
          Style
          <select
            className={inputCls}
            value={form.trip_style ?? ""}
            onChange={(e) => set("trip_style", e.target.value)}
          >
            {TRIP_STYLES.map((s) => (
              <option key={s} value={s}>
                {s || "any"}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div>
        <p className="text-xs text-slate-600">Interests</p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {interests.map((tag) => (
            <button
              type="button"
              key={tag}
              onClick={() => setInterests((list) => list.filter((t) => t !== tag))}
              className="rounded-full bg-blue-50 px-2.5 py-1 text-xs text-blue-700 hover:bg-blue-100"
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
            className="rounded-md border border-slate-300 px-3 text-sm text-slate-600 hover:bg-slate-50"
          >
            Add
          </button>
        </div>
      </div>

      <label className="block text-xs text-slate-600">
        Constraints
        <textarea
          className={inputCls}
          rows={2}
          placeholder="No early mornings, vegetarian food, one rest day…"
          value={form.constraints ?? ""}
          onChange={(e) => set("constraints", e.target.value)}
        />
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={saving}
        className="w-full rounded-md bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {saving ? "Creating…" : "Create trip"}
      </button>
    </form>
  );
}
