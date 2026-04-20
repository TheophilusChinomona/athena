-- ws_approvals: records approval decisions made in the Hermes dashboard.
-- The approval-listener cron polls this table and applies decisions to draft files.

create table if not exists ws_approvals (
  id                   uuid primary key default gen_random_uuid(),
  artifact_type        text not null default 'draft',  -- 'draft' | 'media' | 'script'
  artifact_ref         text not null,                   -- slug / filename
  artifact_path        text,                            -- absolute path on disk (optional)
  status               text not null,                   -- 'APPROVED' | 'REJECTED' | 'REWRITE'
  reviewer             text not null default 'agent',
  note                 text not null default '',
  reviewed_at          timestamptz not null default now(),
  processed_at         timestamptz,                     -- set by approval-listener when applied
  linked_interaction_id uuid references ws_interactions(id) on delete set null
);

-- index for approval-listener polling unprocessed rows
create index if not exists ws_approvals_unprocessed
  on ws_approvals (processed_at)
  where processed_at is null;

-- index for looking up decisions by artifact
create index if not exists ws_approvals_artifact_ref
  on ws_approvals (artifact_ref);

-- RLS: dashboard service role bypasses; anon role has no access
alter table ws_approvals enable row level security;

create policy "service role full access" on ws_approvals
  for all
  using (auth.role() = 'service_role');
