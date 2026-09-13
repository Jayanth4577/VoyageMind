"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { setToken } from "@/services/api";
import { authApi } from "@/services/trips";

function LoginCard() {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState<"login" | "register">(
    params.get("mode") === "register" ? "register" : "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res =
        mode === "login"
          ? await authApi.login(email, password)
          : await authApi.register(email, password, displayName);
      setToken(res.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-inksoft/70 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25";

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <header className="px-5 pt-5">
        <div className="mx-auto flex max-w-5xl items-center gap-3">
          <ThemeToggle />
          <Link href="/" className="text-xs font-medium text-inksoft hover:text-ink">
            ← Back to home
          </Link>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center p-4">
        <div className="w-full max-w-sm rounded-3xl border border-line bg-surface p-8 shadow-xl shadow-primary/5">
          <div className="text-center">
            <span className="text-3xl">🧭</span>
            <h1 className="mt-2 text-2xl font-bold tracking-tight">VoyageMind</h1>
            <p className="mt-1 text-sm text-inksoft">Plan trips with an AI copilot 🌿</p>
          </div>

          <div className="mt-6 flex rounded-xl bg-surface2 p-1 text-sm">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 rounded-lg py-1.5 font-medium transition ${
                  mode === m ? "bg-surface text-ink shadow" : "text-inksoft"
                }`}
              >
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-5 space-y-3">
            {mode === "register" && (
              <input
                className={inputCls}
                placeholder="Display name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                maxLength={120}
              />
            )}
            <input
              className={inputCls}
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <input
              className={inputCls}
              type="password"
              placeholder={mode === "register" ? "Password (min 8 chars)" : "Password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={mode === "register" ? 8 : 1}
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-xl bg-primary py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/25 transition hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginCard />
    </Suspense>
  );
}
