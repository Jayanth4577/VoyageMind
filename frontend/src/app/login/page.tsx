"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { setToken } from "@/services/api";
import { authApi } from "@/services/trips";

function passwordProblem(pw: string): string | null {
  if (pw.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Za-z]/.test(pw)) return "Password must contain at least one letter.";
  if (!/\d/.test(pw)) return "Password must contain at least one number.";
  return null;
}

type View = "login" | "register" | "forgot" | "reset";

function AuthCard() {
  const router = useRouter();
  const params = useSearchParams();
  const [view, setView] = useState<View>(
    params.get("mode") === "register" ? "register" : "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  // forgot / reset flow
  const [devCode, setDevCode] = useState("");

  const inputCls =
    "w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-inksoft/70 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25";

  function clientValidate(): boolean {
    setError("");
    if (view === "register") {
      if (!displayName.trim()) {
        setError("Please enter a display name.");
        return false;
      }
      const problem = passwordProblem(password);
      if (problem) {
        setError(problem);
        return false;
      }
      if (password !== confirm) {
        setError("Passwords do not match.");
        return false;
      }
    }
    if (view === "reset") {
      const problem = passwordProblem(password);
      if (problem) {
        setError(problem);
        return false;
      }
      if (password !== confirm) {
        setError("Passwords do not match.");
        return false;
      }
      if (!devCode.trim()) {
        setError("Enter the reset code you received.");
        return false;
      }
    }
    return true;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!clientValidate()) return;
    setBusy(true);
    setError("");
    try {
      if (view === "login") {
        const res = await authApi.login(email, password);
        setToken(res.access_token);
        router.push("/dashboard");
      } else if (view === "register") {
        const res = await authApi.register(email, password, displayName);
        setToken(res.access_token);
        router.push("/dashboard");
      } else if (view === "forgot") {
        const res = await authApi.forgotPassword(email);
        setInfo(res.message);
        if (res.dev_code) setDevCode(res.dev_code);
        setView("reset");
      } else if (view === "reset") {
        await authApi.resetPassword(email, devCode.trim(), password);
        setInfo("Password reset — sign in with your new password.");
        setPassword("");
        setConfirm("");
        setDevCode("");
        setView("login");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const titles: Record<View, string> = {
    login: "Welcome back",
    register: "Create your account",
    forgot: "Reset your password",
    reset: "Enter your reset code",
  };

  return (
    <div className="w-full max-w-sm rounded-3xl border border-line bg-surface p-8 shadow-xl shadow-primary/5">
      <div className="text-center">
        <span className="text-3xl">🧭</span>
        <h1 className="mt-2 font-display text-2xl font-bold tracking-tight">VoyageMind</h1>
        <p className="mt-1 text-sm text-inksoft">
          {view === "login" || view === "register"
            ? "Plan trips with an AI copilot"
            : titles[view]}
        </p>
      </div>

      {(view === "login" || view === "register") && (
        <div className="mt-6 flex rounded-xl bg-surface2 p-1 text-sm">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => {
                setView(m);
                setError("");
                setInfo("");
              }}
              className={`flex-1 rounded-lg py-1.5 font-medium transition ${
                view === m ? "bg-surface text-ink shadow" : "text-inksoft"
              }`}
            >
              {m === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={submit} className="mt-5 space-y-3">
        {view === "register" && (
          <input
            className={inputCls}
            placeholder="Display name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={120}
          />
        )}
        {view !== "reset" && (
          <input
            className={inputCls}
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        )}
        {view !== "forgot" && (
          <div>
            <input
              className={inputCls}
              type="password"
              placeholder={
                view === "register"
                  ? "Password (8+ chars, letter & number)"
                  : view === "reset"
                    ? "New password (8+ chars, letter & number)"
                    : "Password"
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={view === "login" ? 1 : 8}
            />
            {view === "reset" && (
              <p className="mt-1.5 rounded-lg bg-accentsoft px-3 py-1.5 text-xs text-ink">
                Code{devCode ? "" : " (sent to your email)"}:{" "}
                {devCode ? (
                  <input
                    value={devCode}
                    onChange={(e) => setDevCode(e.target.value)}
                    maxLength={6}
                    className="w-20 rounded border border-line bg-surface px-1.5 py-0.5 text-center font-mono"
                  />
                ) : null}
              </p>
            )}
          </div>
        )}
        {(view === "register" || view === "reset") && (
          <input
            className={inputCls}
            type="password"
            placeholder="Confirm password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        )}

        {view === "login" && (
          <div className="text-right">
            <button
              type="button"
              onClick={() => {
                setView("forgot");
                setError("");
                setInfo("");
              }}
              className="text-xs font-medium text-primary hover:underline"
            >
              Forgot password?
            </button>
          </div>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}
        {info && <p className="rounded-lg bg-accentsoft p-2.5 text-xs text-ink">{info}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-primary py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/25 transition hover:opacity-90 disabled:opacity-50"
        >
          {busy
            ? "Please wait…"
            : view === "login"
              ? "Sign in"
              : view === "register"
                ? "Create account"
                : view === "forgot"
                  ? "Send reset code"
                  : "Reset password"}
        </button>

        {(view === "forgot" || view === "reset") && (
          <button
            type="button"
            onClick={() => {
              setView("login");
              setError("");
              setInfo("");
            }}
            className="w-full text-center text-xs text-inksoft hover:text-ink"
          >
            ← Back to sign in
          </button>
        )}
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginShell />
    </Suspense>
  );
}

function LoginShell() {
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
        <AuthCard />
      </main>
    </div>
  );
}
