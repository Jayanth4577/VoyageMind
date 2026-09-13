"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { getToken } from "@/services/api";

const FEATURES = [
  {
    icon: "🤖",
    title: "AI Auto-Plan",
    text: "Describe your dream trip — the agent pipeline searches real transport, stays and places, checks the weather, and hands you a complete day-by-day plan.",
  },
  {
    icon: "🧩",
    title: "Build-It-Yourself",
    text: "A drag-and-drop timeline where every activity is structured data: times, costs, coordinates and weather sensitivity.",
  },
  {
    icon: "✨",
    title: "AI Copilot, on your terms",
    text: "Ask anything mid-planning. The copilot proposes changes — you accept, reject or edit. It never touches your plan silently.",
  },
  {
    icon: "🌦",
    title: "Live weather & maps",
    text: "Real forecasts, real road times and real places via our Travel MCP gateway — Open-Meteo, OSRM and OpenStreetMap under the hood.",
  },
  {
    icon: "💰",
    title: "Deterministic budget",
    text: "Every rupee is computed by the budget engine, never hallucinated. See spend by category, per day, and savings candidates instantly.",
  },
  {
    icon: "🌳",
    title: "Contingencies & what-if",
    text: "Rain tomorrow? Flight delayed 3 hours? Get structured fallback plans and impact chains — not vague paragraphs.",
  },
];

const MODES = [
  {
    tag: "Mode A",
    title: "Let AI plan it all",
    text: "One prompt in, a validated multi-day itinerary out — transport, stays, activities, weather-checked.",
  },
  {
    tag: "Mode B",
    title: "Build it yourself",
    text: "Full manual control on a visual timeline. Mix your own spots with AI recommendations.",
  },
  {
    tag: "Mode C",
    title: "Build together",
    text: "You drive, the copilot rides shotgun — flagging conflicts and proposing fixes you approve.",
  },
];

export default function LandingPage() {
  // Token check only after mount: localStorage isn't available during SSR.
  const [authed, setAuthed] = useState(false);
  useEffect(() => {
    let active = true;
    (async () => {
      await Promise.resolve();
      if (active) setAuthed(!!getToken());
    })();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-bg text-ink">
      {/* Nav — theme toggle + auth buttons, top left (per design request) */}
      <header className="sticky top-0 z-40 border-b border-line/60 bg-bg/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-5 py-3">
          <ThemeToggle />
          {authed ? (
            <Link
              href="/dashboard"
              className="rounded-full bg-primary px-4 py-1.5 text-sm font-semibold text-white transition hover:opacity-90"
            >
              Open app
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full border border-line px-4 py-1.5 text-sm font-medium text-ink transition hover:bg-surface2"
              >
                Sign in
              </Link>
              <Link
                href="/login?mode=register"
                className="rounded-full bg-primary px-4 py-1.5 text-sm font-semibold text-white transition hover:opacity-90"
              >
                Get started
              </Link>
            </>
          )}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-lg">🧭</span>
            <span className="text-lg font-bold tracking-tight">VoyageMind</span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 right-0 h-96 w-96 rounded-full bg-primary/15 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute top-40 -left-24 h-80 w-80 rounded-full bg-accent/15 blur-3xl"
        />
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 md:grid-cols-2 md:py-28">
          <div>
            <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-inksoft">
              🌿 AI travel workspace · plans, budgets & fallbacks
            </p>
            <h1 className="text-4xl leading-tight font-extrabold tracking-tight md:text-5xl">
              Trips planned{" "}
              <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                with nature&apos;s calm
              </span>{" "}
              and an AI copilot.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-inksoft">
              VoyageMind plans, budgets and stress-tests your journey with real weather,
              real routes and real prices — while you stay in control of every change.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href={authed ? "/dashboard" : "/login?mode=register"}
                className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-primary/25 transition hover:opacity-90"
              >
                Start planning free
              </Link>
              <Link
                href="/login"
                className="rounded-full border border-line bg-surface px-6 py-3 text-sm font-semibold text-ink transition hover:bg-surface2"
              >
                Sign in
              </Link>
            </div>
          </div>

          {/* Stylized product preview */}
          <div className="relative">
            <div className="rounded-3xl border border-line bg-surface p-5 shadow-2xl shadow-primary/10">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">🌿 Goa, November · 4 travelers</p>
                <span className="rounded-full bg-primarysoft px-2.5 py-0.5 text-[11px] font-semibold text-primary">
                  on budget
                </span>
              </div>
              <div className="mt-4 space-y-2.5">
                {[
                  ["🏖️", "Baga Beach", "10:00 – 12:00", "free"],
                  ["🏛️", "Aguada Fort", "12:30 – 14:00", "free"],
                  ["🍽️", "Seafood shack lunch", "14:00 – 15:00", "₹1,200"],
                  ["🛕", "Panaji heritage walk", "16:30 – 18:00", "₹300"],
                ].map(([icon, name, time, cost]) => (
                  <div
                    key={name}
                    className="flex items-center gap-3 rounded-xl border border-line bg-surface2 px-3 py-2.5"
                  >
                    <span>{icon}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{name}</p>
                      <p className="text-[11px] text-inksoft">{time}</p>
                    </div>
                    <span className="text-xs font-semibold text-primary">{cost}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between rounded-xl bg-primarysoft px-3 py-2.5 text-xs font-medium text-primary">
                <span>🌧 Rain flagged Day 4 → museum fallback ready</span>
                <span>₹45,800 left</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          Everything a trip needs, nothing it doesn&apos;t
        </h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-line bg-surface p-5 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/5"
            >
              <span className="text-2xl">{f.icon}</span>
              <h3 className="mt-3 font-semibold">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-inksoft">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Modes */}
      <section className="border-y border-line bg-surface2/60">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Three ways to plan. One workspace.
          </h2>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {MODES.map((m) => (
              <div key={m.tag} className="rounded-2xl border border-line bg-surface p-6">
                <span className="rounded-full bg-accentsoft px-3 py-1 text-xs font-bold text-accent">
                  {m.tag}
                </span>
                <h3 className="mt-3 text-lg font-semibold">{m.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-inksoft">{m.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-5 py-20 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Your next trip is one prompt away.</h2>
        <p className="mx-auto mt-3 max-w-xl text-inksoft">
          Free to start. Works without API keys. Brings its own weather, maps and budget engine.
        </p>
        <Link
          href={authed ? "/dashboard" : "/login?mode=register"}
          className="mt-8 inline-block rounded-full bg-primary px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-primary/25 transition hover:opacity-90"
        >
          Plan my trip →
        </Link>
      </section>

      <footer className="border-t border-line py-8 text-center text-xs text-inksoft">
        🧭 VoyageMind — AI Travel Planning Workspace · built with Next.js, FastAPI & MCP
      </footer>
    </div>
  );
}
