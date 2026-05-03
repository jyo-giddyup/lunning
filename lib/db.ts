import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!url || !serviceKey) {
  throw new Error(
    "Missing Supabase env vars. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
  );
}

// Server-only client. Uses service role key — never import this from a client component.
export const db = createClient(url, serviceKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

export type Game = {
  id: string;
  title: string;
  sides: string[];
  created_at: string;
};

export type GameEvent = {
  id: string;
  game_id: string;
  kind: "score" | "note";
  side_index: number;
  delta: number;
  note: string | null;
  created_at: string;
};
