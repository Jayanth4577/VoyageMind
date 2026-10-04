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

const DESTINATIONS = [
  {
    src: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1200&auto=format&fit=crop",
    name: "Shores & Sun",
    caption: "Beach days planned around the tides and the weather",
  },
  {
    src: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=1200&auto=format&fit=crop",
    name: "Mountain Air",
    caption: "Hikes routed by real road times, not guesswork",
  },
  {
    src: "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?q=80&w=1200&auto=format&fit=crop",
    name: "Heritage & Culture",
    caption: "Temples, forts and old towns with local insight",
  },
  {
    src: "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?q=80&w=1200&auto=format&fit=crop",
    name: "City Nights",
    caption: "Food, markets and nightlife, budgeted to the rupee",
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

  const dashboardHref = authed ? "/dashboard" : "/login?mode=register";

  return (
    <div className="min-h-screen bg-bg text-ink">
      {/* Nav — theme toggle + auth buttons, top left (per design request) */}
      <header className="sticky top-0 z-40 border-b border-line/60 bg-bg/85 backdrop-blur">
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
            <span className="font-display text-lg font-bold tracking-tight">VoyageMind</span>
          </div>
        </div>
      </header>

      {/* Hero — full-bleed travel imagery */}
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage:
              "url(https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?q=80&w=2000&auto=format&fit=crop)",
          }}
          aria-hidden
        />
        <div
          className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/60 to-black/30"
          aria-hidden
        />
        <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-5 py-24 md:grid-cols-[1.2fr_1fr] md:py-32">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-medium text-white/90 backdrop-blur">
              🌿 AI travel workspace · plans, budgets & fallbacks
            </p>
            <h1 className="text-4xl leading-tight font-extrabold tracking-tight text-white md:text-6xl">
              Trips planned with{" "}
              <span className="bg-gradient-to-r from-accent via-yellow-300 to-accent bg-clip-text text-transparent">
                gold-standard care
              </span>{" "}
              and an AI copilot.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-white/80">
              VoyageMind plans, budgets and stress-tests your journey with real weather,
              real routes and real prices — while you stay in control of every change.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href={dashboardHref}
                className="rounded-full bg-primary px-7 py-3 text-sm font-semibold text-white shadow-xl shadow-black/30 ring-1 ring-white/20 transition hover:opacity-90"
              >
                Start planning free
              </Link>
              <Link
                href="/login"
                className="rounded-full border border-white/30 bg-white/10 px-7 py-3 text-sm font-semibold text-white backdrop-blur transition hover:bg-white/20"
              >
                Sign in
              </Link>
            </div>
          </div>

          {/* Stylized itinerary preview card */}
          <div className="rounded-3xl border border-white/15 bg-black/45 p-5 shadow-2xl backdrop-blur-md">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-white">🌿 Goa, November · 4 travelers</p>
              <span className="rounded-full bg-accent/25 px-2.5 py-0.5 text-[11px] font-semibold text-accent">
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
                  className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/10 px-3 py-2.5"
                >
                  <span>{icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white">{name}</p>
                    <p className="text-[11px] text-white/60">{time}</p>
                  </div>
                  <span className="text-xs font-semibold text-accent">{cost}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between rounded-xl bg-accent/15 px-3 py-2.5 text-xs font-medium text-accent">
              <span>🌧 Rain flagged Day 4 → museum fallback ready</span>
              <span>₹45,800 left</span>
            </div>
          </div>
        </div>
      </section>

      {/* Destinations strip with imagery */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="flex items-end justify-between">
          <h2 className="text-3xl font-bold tracking-tight">Every kind of journey</h2>
          <span className="hidden text-sm text-inksoft md:block">planned down to the minute</span>
        </div>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {DESTINATIONS.map((d) => (
            <figure
              key={d.name}
              className="group relative overflow-hidden rounded-2xl border border-line"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={d.src}
                alt={d.name}
                loading="lazy"
                className="h-56 w-full object-cover transition duration-500 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-transparent" />
              <figcaption className="absolute inset-x-0 bottom-0 p-4">
                <p className="font-display text-lg font-bold text-white">{d.name}</p>
                <p className="mt-0.5 text-xs text-white/75">{d.caption}</p>
              </figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="border-y border-line bg-surface2/50">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Everything a trip needs, nothing it doesn&apos;t
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-line bg-surface p-5 transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lg"
              >
                <span className="text-2xl">{f.icon}</span>
                <h3 className="mt-3 font-semibold">{f.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-inksoft">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modes */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <h2 className="text-center text-3xl font-bold tracking-tight">
          Three ways to plan. One workspace.
        </h2>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {MODES.map((m) => (
            <div key={m.tag} className="rounded-2xl border border-line bg-surface p-6">
              <span className="rounded-full bg-primarysoft px-3 py-1 text-xs font-bold text-primary">
                {m.tag}
              </span>
              <h3 className="mt-3 text-lg font-semibold">{m.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-inksoft">{m.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA band over imagery */}
      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage:
              "url(https://images.unsplash.com/photo-1503220317375-aaad61436b1b?q=80&w=2000&auto=format&fit=crop)",
          }}
          aria-hidden
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/80 via-black/70 to-black/85" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-5 py-24 text-center">
          <h2 className="font-display text-3xl font-bold tracking-tight text-white md:text-4xl">
            Your next trip is one prompt away.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-white/75">
            Free to start. Works without API keys. Brings its own weather, maps and budget engine.
          </p>
          <Link
            href={dashboardHref}
            className="mt-8 inline-block rounded-full bg-accent px-9 py-3.5 text-sm font-bold text-black shadow-xl shadow-black/40 transition hover:brightness-110"
          >
            Plan my trip →
          </Link>
        </div>
      </section>

      <footer className="border-t border-line py-8 text-center text-xs text-inksoft">
        🧭 VoyageMind — AI Travel Planning Workspace · built with Next.js, FastAPI & MCP
      </footer>
    </div>
  );
}
