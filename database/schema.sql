-- ═══════════════════════════════════════════════════════════════════════
-- FinTrack — Complete Supabase Schema
-- Run the ENTIRE script in Supabase SQL Editor to set up or refresh
-- every piece of the database: tables, indexes, storage bucket, and
-- permissions.
--
-- Auth identity comes from Firebase; user_id columns store the Firebase
-- UID as TEXT (not a Supabase auth.users UUID).  RLS is disabled across
-- all tables because Firebase handles auth — the Supabase anon key is
-- used for all data operations.
-- ═══════════════════════════════════════════════════════════════════════

-- ──────────────────────────────────────────────────────────────────────
-- 1. DIAGNOSTIC — detect old Flutter/Supabase-Auth columns
--    Run this first if you're migrating from an older version.  All
--    id / user_id columns should say "text".  If any say "uuid", run
--    the drop block below before creating the new tables.
-- ──────────────────────────────────────────────────────────────────────
-- select table_name, column_name, data_type
-- from information_schema.columns
-- where table_schema = 'public'
--   and table_name in ('profiles', 'transactions', 'custom_categories', 'budgets')
--   and column_name in ('id', 'user_id')
-- order by table_name, column_name;


-- ──────────────────────────────────────────────────────────────────────
-- 2. CLEANUP — only needed for migration from the old Flutter version.
--    ⚠️ Drops ALL existing data — back up first if needed!
-- ──────────────────────────────────────────────────────────────────────
-- drop table if exists transactions cascade;
-- drop table if exists custom_categories cascade;
-- drop table if exists budgets cascade;
-- drop table if exists profiles cascade;


-- ──────────────────────────────────────────────────────────────────────
-- 3. TABLES
-- ──────────────────────────────────────────────────────────────────────

create table if not exists profiles (
  id text primary key,                -- Firebase UID
  username text,
  avatar_url text,
  currency text default 'PKR',
  created_at timestamp default now()
);

create table if not exists transactions (
  id uuid default gen_random_uuid() primary key,
  user_id text not null,              -- Firebase UID
  type text not null check (type in ('income', 'expense')),
  category text not null,
  amount numeric not null,
  description text,
  date date not null,
  created_at timestamp default now()
);

create table if not exists custom_categories (
  id uuid default gen_random_uuid() primary key,
  user_id text not null,              -- Firebase UID
  name text not null,
  emoji text not null,
  type text not null check (type in ('income', 'expense')),
  created_at timestamp default now()
);

create table if not exists budgets (
  id uuid default gen_random_uuid() primary key,
  user_id text not null,              -- Firebase UID
  category text not null,
  monthly_limit numeric not null,
  created_at timestamp default now(),
  updated_at timestamp default now(),
  unique(user_id, category)
);


-- ──────────────────────────────────────────────────────────────────────
-- 4. ROW-LEVEL SECURITY — disabled (Firebase handles identity)
-- ──────────────────────────────────────────────────────────────────────

alter table profiles disable row level security;
alter table transactions disable row level security;
alter table custom_categories disable row level security;
alter table budgets disable row level security;


-- ──────────────────────────────────────────────────────────────────────
-- 5. INDEXES
-- ──────────────────────────────────────────────────────────────────────

create index if not exists idx_transactions_user_id on transactions(user_id);
create index if not exists idx_transactions_date on transactions(date);
create index if not exists idx_custom_categories_user_id on custom_categories(user_id);
create index if not exists idx_budgets_user_id on budgets(user_id);


-- ──────────────────────────────────────────────────────────────────────
-- 6. STORAGE — avatars bucket
--    Required for profile photo uploads.  Creates the bucket and allows
--    anon-key uploads (matching the RLS-off model used everywhere else).
-- ──────────────────────────────────────────────────────────────────────

insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do update set public = true;

drop policy if exists "avatars_insert_anon" on storage.objects;
create policy "avatars_insert_anon"
  on storage.objects for insert
  to anon, authenticated
  with check (bucket_id = 'avatars');

drop policy if exists "avatars_update_anon" on storage.objects;
create policy "avatars_update_anon"
  on storage.objects for update
  to anon, authenticated
  using (bucket_id = 'avatars');

drop policy if exists "avatars_select_anon" on storage.objects;
create policy "avatars_select_anon"
  on storage.objects for select
  to anon, authenticated
  using (bucket_id = 'avatars');

drop policy if exists "avatars_delete_anon" on storage.objects;
create policy "avatars_delete_anon"
  on storage.objects for delete
  to anon, authenticated
  using (bucket_id = 'avatars');


-- ═══════════════════════════════════════════════════════════════════════
-- Done.  Verify with:
--   select table_name, column_name, data_type
--   from information_schema.columns
--   where table_schema = 'public'
--     and table_name in ('profiles', 'transactions', 'custom_categories', 'budgets');
--   select id, name, public from storage.buckets where id = 'avatars';
-- ═══════════════════════════════════════════════════════════════════════
