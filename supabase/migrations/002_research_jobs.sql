-- Research Jobs Table
-- Stores background research jobs so results survive mobile backgrounding

create table if not exists research_jobs (
  id uuid primary key,
  query text not null,
  mode text default 'fast',
  status text default 'pending',  -- pending, running, complete, error
  progress jsonb default '[]'::jsonb,
  result jsonb,
  error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Auto-cleanup: delete jobs older than 24 hours (optional, run manually or via cron)
-- delete from research_jobs where created_at < now() - interval '24 hours';
