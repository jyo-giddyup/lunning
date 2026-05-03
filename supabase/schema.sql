-- lunning v1 schema. Run in Supabase SQL editor or via psql.
-- Append-only event log. Games are public-by-URL; no auth in v1.

create extension if not exists pgcrypto;

create table if not exists games (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    sides jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists events (
    id uuid primary key default gen_random_uuid(),
    game_id uuid not null references games(id) on delete cascade,
    kind text not null check (kind in ('score', 'note')),
    side_index integer not null default 0,
    delta integer not null default 0,
    note text,
    created_at timestamptz not null default now()
);

create index if not exists events_game_id_created_at_idx
    on events (game_id, created_at);

-- Append-only: forbid updates and deletes from anon/authenticated roles.
-- Server uses service_role which bypasses RLS for the small set of writes
-- defined in lib/actions.ts. Public URL viewers read via anon role.
alter table games enable row level security;
alter table events enable row level security;

create policy if not exists "games are publicly readable"
    on games for select to anon, authenticated using (true);

create policy if not exists "events are publicly readable"
    on events for select to anon, authenticated using (true);

-- No insert/update/delete policies for anon — only the service role can write.
