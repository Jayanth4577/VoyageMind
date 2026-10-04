"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { getToken } from "@/services/api";
import { authApi, type Me } from "@/services/trips";

export default function ProfilePage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameSaved, setNameSaved] = useState(false);
  // password form
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMessage, setPwMessage] = useState("");
  const [pwError, setPwError] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    let active = true;
    authApi
      .me()
      .then((m) => {
        if (!active) return;
        setMe(m);
        setName(m.display_name);
      })
      .catch((e) => active && setError(e instanceof Error ? e.message : "Failed to load"));
    return () => {
      active = false;
    };
  }, [router]);

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSavingName(true);
    setNameSaved(false);
    try {
      const updated = await authApi.updateMe(name.trim());
      setMe(updated);
      setNameSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingName(false);
    }
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError("");
    setPwMessage("");
    if (newPw.length < 8 || !/[A-Za-z]/.test(newPw) || !/\d/.test(newPw)) {
      setPwError("New password must be 8+ characters with a letter and a number.");
      return;
    }
    if (newPw !== confirmPw) {
      setPwError("New passwords do not match.");
      return;
    }
    setPwBusy(true);
    try {
      await authApi.changePassword(currentPw, newPw);
      setPwMessage("Password changed successfully.");
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Change failed");
    } finally {
      setPwBusy(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-inksoft/70 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25";

  return (
    <AppShell>
      <main className="mx-auto max-w-3xl p-5 md:p-8">
        <h1 className="font-display text-2xl font-bold tracking-tight md:text-3xl">
          👤 Profile
        </h1>
        <p className="mt-1 text-sm text-inksoft">Your account details and security.</p>

        {error && <p className="mt-4 rounded-xl bg-dangersoft p-3 text-sm text-danger">{error}</p>}
        {!me && !error && <p className="mt-6 text-sm text-inksoft">Loading profile…</p>}

        {me && (
          <>
            {/* Identity card */}
            <div className="mt-6 flex items-center gap-4 rounded-2xl border border-line bg-surface p-5">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent text-2xl font-bold text-white">
                {(me.display_name || me.email)[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate font-display text-lg font-bold">
                  {me.display_name || "Traveler"}
                </p>
                <p className="truncate text-sm text-inksoft">{me.email}</p>
                <p className="mt-0.5 text-xs text-inksoft/80">
                  Member since {new Date(me.created_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}{" "}
                  · {me.trip_count} trip{me.trip_count === 1 ? "" : "s"}
                </p>
              </div>
            </div>

            {/* Edit display name */}
            <form
              onSubmit={saveName}
              className="mt-4 rounded-2xl border border-line bg-surface p-5"
            >
              <h2 className="font-semibold">Display name</h2>
              <div className="mt-3 flex gap-2">
                <input
                  className={inputCls}
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    setNameSaved(false);
                  }}
                  maxLength={120}
                />
                <button
                  type="submit"
                  disabled={savingName || !name.trim()}
                  className="shrink-0 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                >
                  {savingName ? "Saving…" : "Save"}
                </button>
              </div>
              {nameSaved && <p className="mt-2 text-xs text-primary">✓ Saved</p>}
            </form>

            {/* Change password */}
            <form
              onSubmit={changePassword}
              className="mt-4 space-y-3 rounded-2xl border border-line bg-surface p-5"
            >
              <h2 className="font-semibold">Change password</h2>
              <input
                className={inputCls}
                type="password"
                placeholder="Current password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  className={inputCls}
                  type="password"
                  placeholder="New password (8+ chars, letter & number)"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  required
                  minLength={8}
                />
                <input
                  className={inputCls}
                  type="password"
                  placeholder="Confirm new password"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  required
                />
              </div>
              {pwError && <p className="text-sm text-danger">{pwError}</p>}
              {pwMessage && <p className="text-sm text-primary">✓ {pwMessage}</p>}
              <button
                type="submit"
                disabled={pwBusy}
                className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              >
                {pwBusy ? "Changing…" : "Change password"}
              </button>
            </form>
          </>
        )}
      </main>
    </AppShell>
  );
}
