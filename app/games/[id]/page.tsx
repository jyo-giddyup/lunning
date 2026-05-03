import { notFound } from "next/navigation";
import { getGameWithEvents } from "@/lib/actions";
import { Scoreboard } from "./scoreboard";

export const dynamic = "force-dynamic";

export default async function GamePage({ params }: { params: { id: string } }) {
  const data = await getGameWithEvents(params.id);
  if (!data) notFound();
  const { game, events } = data;

  const scores = game.sides.map((_, i) =>
    events.filter((e) => e.kind === "score" && e.side_index === i).reduce((sum, e) => sum + e.delta, 0),
  );

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">{game.title}</h1>
        <p className="text-sm text-neutral-500">
          Created {new Date(game.created_at).toLocaleString()} · share this URL to let others view live
        </p>
      </header>

      <Scoreboard gameId={game.id} sides={game.sides} initialScores={scores} />

      <section className="mt-10">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Audit log ({events.length})
        </h2>
        <ol className="space-y-1 text-sm font-mono">
          {events.length === 0 && <li className="text-neutral-400">No events yet.</li>}
          {events.map((e) => (
            <li key={e.id} className="flex justify-between gap-4 border-b border-neutral-200 py-1">
              <span className="text-neutral-500">{new Date(e.created_at).toLocaleTimeString()}</span>
              <span className="flex-1">
                {e.kind === "score" && (
                  <>
                    {e.delta > 0 ? "+" : ""}
                    {e.delta} → {game.sides[e.side_index] ?? `side ${e.side_index}`}
                  </>
                )}
                {e.kind === "note" && <em>{e.note}</em>}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
