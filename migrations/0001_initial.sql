-- Dashboard Analyzer POC schema.
-- Run with a migration runner against PostgreSQL/Supabase. No provider secret
-- is stored here. Application-generated text IDs avoid requiring pgcrypto.

create table if not exists topics (
  id text primary key,
  name text not null check (char_length(name) between 2 and 100),
  keywords text[] not null default '{}',
  product_terms text[] not null default '{}',
  exclude_terms text[] not null default '{}',
  cities text[] not null default '{}',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists source_runs (
  id text primary key,
  topic_id text not null references topics(id) on delete cascade,
  source text not null check (source in ('tiktok','instagram','facebook','maps','shopee','youtube')),
  status text not null check (status in ('disabled','misconfigured','queued','running','fresh','empty','stale','budget_exhausted','error')),
  trigger text not null default 'manual' check (trigger in ('manual','scheduled','startup')),
  provider_run_id text,
  raw_count integer not null default 0 check (raw_count >= 0),
  relevant_count integer not null default 0 check (relevant_count >= 0),
  inserted_count integer not null default 0 check (inserted_count >= 0),
  error_code text,
  message text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table if not exists evidence (
  id text primary key,
  topic_id text not null references topics(id) on delete cascade,
  source text not null check (source in ('tiktok','instagram','facebook','maps','shopee','youtube')),
  external_id text not null,
  provider_run_id text,
  title text,
  text text,
  author text,
  url text not null check (url ~* '^https?://'),
  published_at timestamptz,
  collected_at timestamptz not null default now(),
  relevance_score double precision check (relevance_score between 0 and 1),
  views bigint check (views >= 0),
  likes bigint check (likes >= 0),
  comments bigint check (comments >= 0),
  shares bigint check (shares >= 0),
  rating numeric(3,2) check (rating between 0 and 5),
  review_count bigint check (review_count >= 0),
  price bigint check (price >= 0),
  original_price bigint check (original_price >= 0),
  sold bigint check (sold >= 0),
  metadata jsonb not null default '{}'::jsonb,
  unique (topic_id, source, external_id),
  check (nullif(trim(coalesce(title, '') || ' ' || coalesce(text, '')), '') is not null)
);

create table if not exists evidence_metric_snapshots (
  id bigint generated always as identity primary key,
  evidence_id text not null references evidence(id) on delete cascade,
  captured_at timestamptz not null default now(),
  views bigint check (views >= 0),
  likes bigint check (likes >= 0),
  comments bigint check (comments >= 0),
  shares bigint check (shares >= 0),
  rating numeric(3,2) check (rating between 0 and 5),
  review_count bigint check (review_count >= 0),
  price bigint check (price >= 0),
  sold bigint check (sold >= 0)
);

create table if not exists analyses (
  evidence_id text primary key references evidence(id) on delete cascade,
  label text not null check (label in ('positif','negatif','netral','pending')),
  score double precision not null check (score between -1 and 1),
  confidence double precision not null check (confidence between 0 and 1),
  aspects text[] not null default '{}',
  analyzer text not null check (analyzer in ('gemini','local_fallback','pending')),
  analyzed_at timestamptz not null default now()
);

create table if not exists provider_usage (
  provider text not null,
  source text not null default 'global' check (source = 'global' or source in ('tiktok','instagram','facebook','maps','shopee','youtube')),
  usage_date date not null,
  requests integer not null default 0 check (requests >= 0),
  units integer not null default 0 check (units >= 0),
  primary key (provider, source, usage_date)
);

create index if not exists idx_topics_active_created on topics (created_at desc) where is_active = true;
create index if not exists idx_source_runs_topic_source_started on source_runs (topic_id, source, started_at desc);
create index if not exists idx_evidence_topic_collected on evidence (topic_id, collected_at desc);
create index if not exists idx_evidence_topic_source_collected on evidence (topic_id, source, collected_at desc);
create index if not exists idx_evidence_metric_evidence_captured on evidence_metric_snapshots (evidence_id, captured_at desc);
create index if not exists idx_provider_usage_date on provider_usage (usage_date, provider);

-- The API uses a server-side database role. If the public schema is exposed
-- through Supabase, keep RLS enabled and add narrowly scoped policies later
-- when authenticated tenants are introduced.
alter table topics enable row level security;
alter table source_runs enable row level security;
alter table evidence enable row level security;
alter table evidence_metric_snapshots enable row level security;
alter table analyses enable row level security;
alter table provider_usage enable row level security;

comment on table topics is 'User-defined UMKM product monitoring topics';
comment on table evidence is 'Traceable public evidence collected by a source adapter';
comment on table analyses is 'Sentiment/aspect results, optionally produced by Gemini';
