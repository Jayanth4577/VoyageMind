"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { copilotApi, type CopilotMessage, type Suggestion } from "@/services/copilot";

interface Props {
  tripId: string;
  /** Prompt queued by another tab (e.g. "Ask AI to fix conflicts" from the builder). */
  pendingPrompt?: string | null;
  onPromptConsumed?: () => void;
  onItineraryChanged?: () => void;
}

function SuggestionCard({
  tripId,
  suggestion,
  onResolved,
}: {
  tripId: string;
  suggestion: Suggestion;
  onResolved: (accepted: boolean, summary?: string) => void;
}) {
  const [busy, setBusy] = useState<"accept" | "reject" | null>(null);
  const [cascade, setCascade] = useState<string | null>(null);

  async function act(action: "accept" | "reject") {
    setBusy(action);
    try {
      const res = await copilotApi.suggestionAction(tripId, suggestion.suggestion_id, action);
      if (action === "accept") {
        const budget = (res.cascade as { budget?: { spent?: number; state?: string } })?.budget;
        setCascade(
          `Applied ${res.applied_changes} change(s). Budget now ${budget?.state ?? "?"} at ${budget?.spent ?? "?"}.`,
        );
        onResolved(true);
      } else {
        onResolved(false);
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">
      <p className="font-medium text-blue-800">🤖 {suggestion.problem || "Suggested change"}</p>
      {suggestion.reasoning && <p className="mt-1 text-slate-600">{suggestion.reasoning}</p>}
      <ul className="mt-2 space-y-1">
        {suggestion.changes.map((change, i) => (
          <li key={i} className="text-slate-700">
            <span className="rounded bg-white px-1.5 py-0.5 text-xs font-medium text-blue-700">
              {change.change_type.replaceAll("_", " ")}
            </span>{" "}
            {String(change.proposed_data?.name ?? change.target_activity_id ?? "")}
            {change.reason ? ` — ${change.reason}` : ""}
            {change.impact ? ` (${change.impact})` : ""}
          </li>
        ))}
      </ul>
      {cascade ? (
        <p className="mt-2 font-medium text-emerald-700">✓ {cascade}</p>
      ) : (
        <div className="mt-2 flex gap-2">
          <button
            onClick={() => act("accept")}
            disabled={busy !== null}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy === "accept" ? "Applying…" : "Accept"}
          </button>
          <button
            onClick={() => act("reject")}
            disabled={busy !== null}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            Reject
          </button>
          <span className="self-center text-xs text-slate-400">AI never edits without your approval</span>
        </div>
      )}
    </div>
  );
}

export default function AICopilot({
  tripId,
  pendingPrompt,
  onPromptConsumed,
  onItineraryChanged,
}: Props) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToEnd = () =>
    requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }));

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const history = await copilotApi.history(tripId);
        if (!active) return;
        setMessages(history);
        scrollToEnd();
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load history");
      }
    })();
    return () => {
      active = false;
    };
  }, [tripId]);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || busy) return;
      setBusy(true);
      setError("");
      // optimistic user bubble
      setMessages((m) => [
        ...m,
        {
          id: `tmp-${Date.now()}`,
          trip_id: tripId,
          role: "user",
          content: message,
          data: {},
          created_at: new Date().toISOString(),
        },
      ]);
      scrollToEnd();
      try {
        const res = await copilotApi.send(tripId, message);
        setMessages((m) => [...m, res.message]);
        if (res.suggestions?.length) onItineraryChanged?.();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Copilot unavailable");
      } finally {
        setBusy(false);
        scrollToEnd();
      }
    },
    [tripId, busy, onItineraryChanged],
  );

  // Send prompts queued from other tabs (e.g. "fix the conflicts on Day 2").
  // setState calls run only after the microtask boundary, keeping the effect side-effect-free.
  useEffect(() => {
    if (!pendingPrompt) return;
    let active = true;
    (async () => {
      await Promise.resolve();
      if (!active) return;
      await send(pendingPrompt);
      onPromptConsumed?.();
    })();
    return () => {
      active = false;
    };
  }, [pendingPrompt, send, onPromptConsumed]);

  return (
    <div className="flex h-[32rem] flex-col rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-100 p-4">
        <h2 className="font-semibold text-slate-800">🤖 AI Copilot</h2>
        <p className="text-xs text-slate-500">
          Knows your trip state · uses real tools for weather, routes and prices · proposes changes
          for approval
        </p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">
            <p className="font-medium text-slate-600">Try asking:</p>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>&ldquo;Is this itinerary realistic?&rdquo;</li>
              <li>&ldquo;What should I do after Baga Beach?&rdquo;</li>
              <li>&ldquo;Reduce the trip cost by ₹5,000&rdquo;</li>
              <li>&ldquo;Find something indoors for tomorrow&rdquo;</li>
              <li>&ldquo;What happens if my flight is delayed by 3 hours?&rdquo;</li>
            </ul>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id}>
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "ml-auto bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-800"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.data?.agent && msg.role === "assistant" && (
                <p className="mt-1 text-[10px] uppercase tracking-wide opacity-60">
                  via {msg.data.agent} · {msg.data.tool_calls_count ?? 0} tool calls
                </p>
              )}
            </div>
            {msg.data?.suggestions?.map((s: Suggestion) => (
              <SuggestionCard
                key={s.suggestion_id}
                tripId={tripId}
                suggestion={s}
                onResolved={(accepted) => {
                  if (accepted) onItineraryChanged?.();
                }}
              />
            ))}
          </div>
        ))}
        {busy && <p className="text-xs text-slate-400">Copilot is thinking…</p>}
        {error && <p className="text-xs text-red-600">{error}</p>}
        <div ref={bottomRef} />
      </div>

      <form
        className="flex gap-2 border-t border-slate-100 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
          setInput("");
        }}
      >
        <input
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          placeholder="Ask the copilot…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={2000}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
