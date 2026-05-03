"use client";

import { useState, useTransition } from "react";
import { addScoreEvent } from "@/lib/actions";
import { useRouter } from "next/navigation";

export function Scoreboard({
  gameId,
  sides,
  initialScores,
}: {
  gameId: string;
  sides: string[];
  initialScores: number[];
}) {
  const [scores, setScores] = useState(initialScores);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function bump(sideIndex: number, delta: number) {
    setScores((prev) => prev.map((s, i) => (i === sideIndex ? s + delta : s)));
    startTransition(async () => {
      await addScoreEvent(gameId, sideIndex, delta);
      router.refresh();
    });
  }

  return (
    <section
      aria-label="Live scoreboard"
      aria-live="polite"
      className="grid gap-4"
      style={{ gridTemplateColumns: `repeat(${sides.length}, minmax(0, 1fr))` }}
    >
      {sides.map((name, i) => (
        <div key={i} className="rounded-lg border border-neutral-200 bg-white p-4 text-center">
          <div className="text-sm font-medium text-neutral-600">{name}</div>
          <div className="my-2 text-6xl font-bold tabular-nums" aria-label={`${name} score: ${scores[i]}`}>
            {scores[i]}
          </div>
          <div className="flex justify-center gap-2">
            <button
              onClick={() => bump(i, -1)}
              disabled={isPending || scores[i] === 0}
              aria-label={`Subtract one from ${name}`}
              className="rounded border border-neutral-300 px-3 py-1 text-sm hover:bg-neutral-100 focus:outline-none focus:ring-2 focus:ring-neutral-400 focus:ring-offset-2 disabled:opacity-40"
            >
              −1
            </button>
            <button
              onClick={() => bump(i, 1)}
              disabled={isPending}
              aria-label={`Add one to ${name}`}
              className="rounded bg-neutral-900 px-3 py-1 text-sm text-white hover:bg-neutral-700 focus:outline-none focus:ring-2 focus:ring-neutral-400 focus:ring-offset-2 disabled:opacity-40"
            >
              +1
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
