"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { getToken, setToken } from "@/services/api";

const APP_NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "🏠" },
  { href: "/analytics", label: "Analytics", icon: "📊" },
  { href: "/trips", label: "My Trips", icon: "🧳" },
];

const TRIP_NAV = [
  { seg: "", label: "Overview", icon: "🏞️" },
  { seg: "itinerary", label: "Itinerary", icon: "📅" },
  { seg: "copilot", label: "AI Copilot", icon: "🤖" },
  { seg: "budget", label: "Budget", icon: "💰" },
  { seg: "analysis", label: "Analysis", icon: "📊" },
  { seg: "weather", label: "Weather", icon: "🌦️" },
  { seg: "map", label: "Map", icon: "🗺️" },
  { seg: "risks", label: "Risks & Simulate", icon: "⚠️" },
  { seg: "contingencies", label: "Contingencies", icon: "🌳" },
  { seg: "group", label: "Group", icon: "👥" },
];

interface Props {
  children: React.ReactNode;
  /** When set, the trip-scoped navigation section renders. */
  trip?: { id: string; name: string };
}

export default function AppShell({ children, trip }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  // Evaluated once on the client; individual pages also guard their own fetches.
  const [authed] = useState(() => (typeof window === "undefined" ? true : !!getToken()));

  useEffect(() => {
    if (!getToken()) router.push("/login");
  }, [router]);

  function signOut() {
    setToken(null);
    router.push("/");
  }

  function isActive(href: string) {
    return pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
  }

  function tripHref(seg: string) {
    return `/trips/${trip!.id}${seg ? "/" + seg : ""}`;
  }

  return (
    <div className="flex min-h-screen bg-bg text-ink">
      {/* Sidebar */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <Link href="/" className="flex items-center gap-2 px-5 py-5">
          <span className="text-xl">🧭</span>
          <span className="text-base font-bold tracking-tight">VoyageMind</span>
        </Link>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
          {APP_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition ${
                isActive(item.href)
                  ? "bg-primarysoft text-primary"
                  : "text-inksoft hover:bg-surface2 hover:text-ink"
              }`}
            >
              <span>{item.icon}</span> {item.label}
            </Link>
          ))}

          {trip && (
            <>
              <p className="px-3 pt-5 pb-1 text-[11px] font-semibold tracking-wide text-inksoft uppercase">
                {trip.name.length > 22 ? trip.name.slice(0, 22) + "…" : trip.name}
              </p>
              {TRIP_NAV.map((item) => {
                const href = tripHref(item.seg);
                const active =
                  item.seg === ""
                    ? pathname === href
                    : pathname.startsWith(href);
                return (
                  <Link
                    key={item.seg}
                    href={href}
                    className={`flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition ${
                      active
                        ? "bg-primarysoft text-primary"
                        : "text-inksoft hover:bg-surface2 hover:text-ink"
                    }`}
                  >
                    <span>{item.icon}</span> {item.label}
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        <div className="flex items-center justify-between border-t border-line px-4 py-3">
          <ThemeToggle />
          <button
            onClick={signOut}
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-inksoft transition hover:bg-surface2 hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main + mobile nav */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <div className="sticky top-0 z-40 border-b border-line bg-bg/90 backdrop-blur md:hidden">
          <div className="flex items-center justify-between px-4 py-2.5">
            <Link href="/" className="flex items-center gap-1.5 text-sm font-bold">
              🧭 VoyageMind
            </Link>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <button
                onClick={signOut}
                className="rounded-lg px-2 py-1 text-xs text-inksoft"
              >
                Sign out
              </button>
            </div>
          </div>
          <div className="flex gap-1 overflow-x-auto px-3 pb-2">
            {(trip
              ? [...APP_NAV.map((a) => ({ ...a, href: a.href })), ...TRIP_NAV.map((t) => ({ ...t, href: tripHref(t.seg) }))]
              : APP_NAV
            ).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  isActive(item.href)
                    ? "bg-primarysoft text-primary"
                    : "bg-surface2 text-inksoft"
                }`}
              >
                {item.icon} {item.label}
              </Link>
            ))}
          </div>
        </div>

        <main className="min-w-0 flex-1">{authed || pathname === "/login" ? children : null}</main>
      </div>
    </div>
  );
}
