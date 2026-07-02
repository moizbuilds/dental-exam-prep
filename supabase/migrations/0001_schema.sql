-- MOPH/DHP Dental Qualifying Exam — grounded MCQ bank
-- Core principle: no source, no question. Enforced at the schema layer.

create extension if not exists "pgcrypto";

-- ── questions ────────────────────────────────────────────────────────────────
create table if not exists public.questions (
  id                    uuid primary key default gen_random_uuid(),
  domain                text not null,
  subdomain             text not null,

  stem                  text not null,
  options               jsonb not null,            -- array of exactly 4 strings
  correct_index         smallint not null,
  correct_explanation   text not null,             -- why the right answer is right
  distractor_rationales jsonb not null,            -- why each of the 3 wrong options is wrong

  source_book           text not null,
  source_isbn           text,
  source_edition        text,
  source_page_or_section text,
  source_passage        text not null,             -- the chunk the question was written from
  supporting_quote      text not null,             -- the sentence proving the answer

  verification_status   text not null default 'flagged',  -- pass | fail | flagged
  visual_type           text not null default 'none',     -- none | text_vignette | original_diagram_needed
  diagram_svg           text,

  created_at            timestamptz not null default now(),

  -- grounding guarantees: reject ungrounded inserts
  constraint source_book_not_blank      check (length(btrim(source_book)) > 0),
  constraint source_passage_not_blank   check (length(btrim(source_passage)) > 0),
  constraint supporting_quote_not_blank check (length(btrim(supporting_quote)) > 0),

  -- structural guarantees
  constraint options_is_4 check (jsonb_typeof(options) = 'array' and jsonb_array_length(options) = 4),
  constraint correct_index_range check (correct_index between 0 and 3),
  constraint distractor_rationales_is_array check (jsonb_typeof(distractor_rationales) = 'array'),
  constraint verification_status_enum check (verification_status in ('pass','fail','flagged')),
  constraint visual_type_enum check (visual_type in ('none','text_vignette','original_diagram_needed'))
);

create index if not exists questions_domain_idx on public.questions (domain, subdomain);
create index if not exists questions_status_idx on public.questions (verification_status);

-- ── user_progress ────────────────────────────────────────────────────────────
create table if not exists public.user_progress (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references auth.users(id) on delete cascade,
  question_id       uuid not null references public.questions(id) on delete cascade,
  answered_correctly boolean not null,
  answered_at       timestamptz not null default now()
);

create index if not exists user_progress_user_idx on public.user_progress (user_id);
create index if not exists user_progress_question_idx on public.user_progress (question_id);

-- ── user_flags ───────────────────────────────────────────────────────────────
create table if not exists public.user_flags (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  question_id uuid not null references public.questions(id) on delete cascade,
  reason      text,
  created_at  timestamptz not null default now(),
  unique (user_id, question_id)
);

create index if not exists user_flags_question_idx on public.user_flags (question_id);

-- ── Row Level Security ───────────────────────────────────────────────────────
alter table public.questions     enable row level security;
alter table public.user_progress enable row level security;
alter table public.user_flags    enable row level security;

-- questions: only verified (pass) items are readable by authenticated users.
drop policy if exists "read verified questions" on public.questions;
create policy "read verified questions" on public.questions
  for select to authenticated
  using (verification_status = 'pass');

-- user_progress: each user owns their rows.
drop policy if exists "own progress select" on public.user_progress;
create policy "own progress select" on public.user_progress
  for select to authenticated using (auth.uid() = user_id);
drop policy if exists "own progress insert" on public.user_progress;
create policy "own progress insert" on public.user_progress
  for insert to authenticated with check (auth.uid() = user_id);

-- user_flags: each user owns their rows.
drop policy if exists "own flags select" on public.user_flags;
create policy "own flags select" on public.user_flags
  for select to authenticated using (auth.uid() = user_id);
drop policy if exists "own flags insert" on public.user_flags;
create policy "own flags insert" on public.user_flags
  for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "own flags delete" on public.user_flags;
create policy "own flags delete" on public.user_flags
  for delete to authenticated using (auth.uid() = user_id);
-- Note: questions are inserted only by the Python pipeline via the service-role
-- key, which bypasses RLS. No insert/update policy is granted to clients.
