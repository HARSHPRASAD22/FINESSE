create table if not exists public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  jurisdiction text not null,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner','member','consultant','reviewer','administrator')),
  primary key (workspace_id, user_id)
);

create table if not exists public.assessments (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  profile_revision integer not null,
  status text not null,
  engine_version text not null,
  results jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  uploader_id uuid references auth.users(id),
  filename text not null,
  mime_type text not null,
  size_bytes bigint not null,
  storage_path text not null,
  processing_state text not null,
  extracted jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.agent_sessions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  goal text not null,
  stage text not null,
  memory jsonb not null default '{}'::jsonb,
  messages jsonb not null default '[]'::jsonb,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references public.workspaces(id) on delete cascade,
  actor_id uuid references auth.users(id),
  action text not null,
  resource_type text not null,
  resource_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.source_snapshots (
  id uuid primary key default gen_random_uuid(),
  authority text not null,
  title text not null,
  canonical_url text not null,
  jurisdiction text not null,
  content_hash text not null,
  captured_at timestamptz not null default now(),
  text_excerpt text,
  metadata jsonb not null default '{}'::jsonb
);

alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.assessments enable row level security;
alter table public.documents enable row level security;
alter table public.agent_sessions enable row level security;
alter table public.audit_logs enable row level security;
alter table public.source_snapshots enable row level security;

create or replace function public.is_workspace_member(target_workspace_id uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.workspace_members
    where workspace_id = target_workspace_id
      and user_id = auth.uid()
  );
$$;

revoke all on function public.is_workspace_member(uuid) from public;
grant execute on function public.is_workspace_member(uuid) to authenticated;

drop policy if exists "workspace member read" on public.workspaces;
create policy "workspace member read" on public.workspaces
  for select using (public.is_workspace_member(id));

drop policy if exists "workspace creator insert" on public.workspaces;
create policy "workspace creator insert" on public.workspaces
  for insert with check (created_by = auth.uid());

drop policy if exists "workspace member read own membership" on public.workspace_members;
create policy "workspace member read own membership" on public.workspace_members
  for select using (user_id = auth.uid());

drop policy if exists "workspace owner manage membership" on public.workspace_members;
create policy "workspace owner manage membership" on public.workspace_members
  for all using (
    exists (
      select 1
      from public.workspace_members wm
      where wm.workspace_id = workspace_members.workspace_id
        and wm.user_id = auth.uid()
        and wm.role in ('owner','administrator')
    )
  ) with check (
    exists (
      select 1
      from public.workspace_members wm
      where wm.workspace_id = workspace_members.workspace_id
        and wm.user_id = auth.uid()
        and wm.role in ('owner','administrator')
    )
  );

drop policy if exists "workspace tenant assessments" on public.assessments;
create policy "workspace tenant assessments" on public.assessments
  for all using (public.is_workspace_member(workspace_id))
  with check (public.is_workspace_member(workspace_id));

drop policy if exists "workspace tenant documents" on public.documents;
create policy "workspace tenant documents" on public.documents
  for all using (public.is_workspace_member(workspace_id))
  with check (public.is_workspace_member(workspace_id));

drop policy if exists "workspace tenant agent sessions" on public.agent_sessions;
create policy "workspace tenant agent sessions" on public.agent_sessions
  for all using (public.is_workspace_member(workspace_id))
  with check (public.is_workspace_member(workspace_id));

drop policy if exists "workspace tenant audit" on public.audit_logs;
create policy "workspace tenant audit" on public.audit_logs
  for select using (public.is_workspace_member(workspace_id));

drop policy if exists "authenticated source snapshots" on public.source_snapshots;
create policy "authenticated source snapshots" on public.source_snapshots
  for select using (auth.uid() is not null);
