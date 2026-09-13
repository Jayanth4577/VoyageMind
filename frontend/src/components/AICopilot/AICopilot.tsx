"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { copilotApi, type CopilotMessage, type Suggestion } from "@/services/copilot";

interface Props {
  tripId: string;
  /** Called after a suggestion is accepted so hosts can refresh data. */
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
    <div className="mt-2 rounded-lg border border-primary/30 bg-primarysoft p-3 text-sm">
      <p className="font-medium text-primary">🤖 {suggestion.problem || "Suggested change"}</p>
      {suggestion.reasoning && <p className="mt-1 text-inksoft">{suggestion.reasoning}</p>}
      <ul className="mt-2 space-y-1">
        {suggestion.changes.map((change, i) => (
          <li key={i} className="text-ink">
            <span className="rounded bg-surface px-1.5 py-0.5 text-xs font-medium text-primary">
              {change.change_type.replaceAll("_", " ")}
            </span>{" "}
            {String(change.proposed_data?.name ?? change.target_activity_id ?? "")}
            {change.reason ? ` — ${change.reason}` : ""}
            {change.impact ? ` (${change.impact})` : ""}
          </li>
        ))}
      </ul>
      {cascade ? (
        <p className="mt-2 font-medium text-primary">✓ {cascade}</p>
      ) : (
        <div className="mt-2 flex gap-2">
          <button
            onClick={() => act("accept")}
            disabled={busy !== null}
            className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary disabled:opacity-50"
          >
            {busy === "accept" ? "Applying…" : "Accept"}
          </button>
          <button
            onClick={() => act("reject")}
            disabled={busy !== null}
            className="rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-inksoft hover:bg-surface2 disabled:opacity-50"
          >
            Reject
          </button>
          <span className="self-center text-xs text-inksoft/80">AI never edits without your approval</span>
        </div>
      )}
    </div>
  );
}

export default function AICopilot({ tripId, onItineraryChanged }: Props) {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const queuedPrompt = searchParams.get("prompt");

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

  // Send prompts queued via ?prompt=... (e.g. "fix the conflicts on Day 2").
  // setState calls run only after the microtask boundary, keeping the effect side-effect-free.
  useEffect(() => {
    if (!queuedPrompt) return;
    let active = true;
    (async () => {
      await Promise.resolve();
      if (!active) return;
      await send(queuedPrompt);
      window.history.replaceState(null, "", window.location.pathname);
    })();
    return () => {
      active = false;
    };
  }, [queuedPrompt, send]);

  return (
    <div className="flex h-[32rem] flex-col rounded-xl border border-line bg-surface">
      <div className="border-b border-line p-4">
        <h2 className="font-semibold text-ink">🤖 AI Copilot</h2>
        <p className="text-xs text-inksoft">
          Knows your trip state · uses real tools for weather, routes and prices · proposes changes
          for approval
        </p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="rounded-lg bg-surface2 p-4 text-sm text-inksoft">
            <p className="font-medium text-inksoft">Try asking:</p>
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
                  ? "ml-auto bg-primary text-white"
                  : "bg-surface2 text-ink"
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
        {busy && <p className="text-xs text-inksoft/80">Copilot is thinking…</p>}
        {error && <p className="text-xs text-danger">{error}</p>}
        <div ref={bottomRef} />
      </div>

      <form
        className="flex gap-2 border-t border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
          setInput("");
        }}
      >
        <input
          className="flex-1 rounded-md border border-line px-3 py-2 text-sm focus:border-primary focus:outline-none"
          placeholder="Ask the copilot…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={2000}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
