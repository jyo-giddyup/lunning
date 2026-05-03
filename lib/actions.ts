"use server";

import { revalidatePath } from "next/cache";
import { db, type Game, type GameEvent } from "./db";

export async function createGame(input: { title: string; sides: string[] }): Promise<string> {
  const { data, error } = await db
    .from("games")
    .insert({ title: input.title, sides: input.sides })
    .select("id")
    .single();
  if (error) throw error;
  return data.id as string;
}

export async function getGameWithEvents(
  id: string,
): Promise<{ game: Game; events: GameEvent[] } | null> {
  const [{ data: game, error: gErr }, { data: events, error: eErr }] = await Promise.all([
    db.from("games").select("*").eq("id", id).maybeSingle(),
    db.from("events").select("*").eq("game_id", id).order("created_at", { ascending: true }),
  ]);
  if (gErr || eErr) throw gErr ?? eErr;
  if (!game) return null;
  return { game: game as Game, events: (events ?? []) as GameEvent[] };
}

export async function addScoreEvent(gameId: string, sideIndex: number, delta: number) {
  if (!Number.isInteger(sideIndex) || sideIndex < 0) throw new Error("Bad side index.");
  if (!Number.isInteger(delta) || delta === 0) throw new Error("Delta must be a non-zero integer.");
  const { error } = await db.from("events").insert({
    game_id: gameId,
    kind: "score",
    side_index: sideIndex,
    delta,
  });
  if (error) throw error;
  revalidatePath(`/games/${gameId}`);
}
