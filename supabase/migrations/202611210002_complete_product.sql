create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  preferences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.businesses (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  name text not null,
  business_type text,
  jurisdiction text not null,
  current_profile_version integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.business_profile_versions (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references public.businesses(id) on delete cascade,
  revision integer not null,
  facts jsonb not null,
  missing_facts text[] not null default '{}',
  ambiguous_facts text[] not null default '{}',
  source_description text,
  confirmed_by uuid references auth.users(id),
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(business_id, revision)
);

create table if not exists public.regulatory_sources (
  id uuid primary key default gen_random_uuid(),
  authority text not null,
  title text not null,
  canonical_url text not null,
  jurisdiction text not null,
  trust_level text not null default 'primary',
  created_at timestamptz not null default now()
);

create table if not exists public.regulatory_rules (
  id uuid primary key default gen_random_uuid(),
  stable_key text not null unique,
  title text not null,
  current_version integer not null default 1,
  lifecycle_state text not null default 'candidate',
  created_at timestamptz not null default now()
);

create table if not exists public.regulatory_rule_versions (
  id uuid primary key default gen_random_uuid(),
  rule_id uuid not null references public.regulatory_rules(id) on delete cascade,
  version integer not null,
  conditions jsonb not null default '[]'::jsonb,
  exceptions jsonb not null default '[]'::jsonb,
  source_snapshot_id uuid references public.source_snapshots(id),
  effective_from date,
  effective_to date,
  approval_state text not null default 'candidate',
  reviewed_by uuid references auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(rule_id, version)
);

create table if not exists public.assessment_evidence (
  id uuid primary key default gen_random_uuid(),
  assessment_id uuid not null references public.assessments(id) on delete cascade,
  rule_version_id uuid references public.regulatory_rule_versions(id),
  source_snapshot_id uuid references public.source_snapshots(id),
  provision_reference text,
  excerpt text,
  created_at timestamptz not null default now()
);

create table if not exists public.document_extractions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  extracted_fields jsonb not null default '{}'::jsonb,
  provider text,
  schema_version text,
  confidence jsonb not null default '{}'::jsonb,
  review_state text not null default 'needs_review',
  reviewed_by uuid references auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.document_requirement_links (
  document_id uuid not null references public.documents(id) on delete cascade,
  requirement_key text not null,
  relationship text not null default 'supports',
  primary key(document_id, requirement_key)
);

create table if not exists public.compliance_tasks (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  business_id uuid references public.businesses(id) on delete cascade,
  assessment_id uuid references public.assessments(id) on delete cascade,
  requirement_key text,
  title text not null,
  description text,
  priority text not null default 'medium',
  status text not null default 'open',
  due_date date,
  assignee_id uuid references auth.users(id),
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.reports (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  assessment_id uuid references public.assessments(id) on delete set null,
  report_type text not null,
  storage_path text,
  status text not null default 'ready',
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.simulations (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references public.businesses(id) on delete cascade,
  baseline_profile_version_id uuid references public.business_profile_versions(id),
  scenario_facts jsonb not null,
  baseline_results jsonb not null,
  scenario_results jsonb not null,
  changes jsonb not null,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid references auth.users(id),
  type text not null,
  title text not null,
  payload jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.businesses enable row level security;
alter table public.business_profile_versions enable row level security;
alter table public.assessment_evidence enable row level security;
alter table public.document_extractions enable row level security;
alter table public.document_requirement_links enable row level security;
alter table public.compliance_tasks enable row level security;
alter table public.reports enable row level security;
alter table public.simulations enable row level security;
alter table public.notifications enable row level security;

insert into storage.buckets (id, name, public)
values ('permitpilot-documents', 'permitpilot-documents', false)
on conflict (id) do update set public = excluded.public;

drop policy if exists "profiles own row" on public.profiles;
create policy "profiles own row" on public.profiles
  for all using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists "workspace tenant businesses" on public.businesses;
create policy "workspace tenant businesses" on public.businesses
  for all using (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = businesses.workspace_id and wm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = businesses.workspace_id and wm.user_id = auth.uid()
    )
  );

drop policy if exists "workspace tenant profile versions" on public.business_profile_versions;
create policy "workspace tenant profile versions" on public.business_profile_versions
  for all using (
    exists (
      select 1
      from public.businesses b
      join public.workspace_members wm on wm.workspace_id = b.workspace_id
      where b.id = business_profile_versions.business_id
        and wm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1
      from public.businesses b
      join public.workspace_members wm on wm.workspace_id = b.workspace_id
      where b.id = business_profile_versions.business_id
        and wm.user_id = auth.uid()
    )
  );

drop policy if exists "workspace tenant compliance tasks" on public.compliance_tasks;
create policy "workspace tenant compliance tasks" on public.compliance_tasks
  for all using (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = compliance_tasks.workspace_id and wm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = compliance_tasks.workspace_id and wm.user_id = auth.uid()
    )
  );

drop policy if exists "workspace tenant reports" on public.reports;
create policy "workspace tenant reports" on public.reports
  for all using (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = reports.workspace_id and wm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = reports.workspace_id and wm.user_id = auth.uid()
    )
  );

drop policy if exists "workspace tenant notifications" on public.notifications;
create policy "workspace tenant notifications" on public.notifications
  for all using (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = notifications.workspace_id and wm.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.workspace_members wm
      where wm.workspace_id = notifications.workspace_id and wm.user_id = auth.uid()
    )
  );

drop policy if exists "private document objects read" on storage.objects;
create policy "private document objects read" on storage.objects
  for select using (
    bucket_id = 'permitpilot-documents'
    and auth.uid() is not null
    and split_part(name, '/', 1) = auth.uid()::text
  );

drop policy if exists "private document objects insert" on storage.objects;
create policy "private document objects insert" on storage.objects
  for insert with check (
    bucket_id = 'permitpilot-documents'
    and auth.uid() is not null
    and split_part(name, '/', 1) = auth.uid()::text
  );

drop policy if exists "private document objects update" on storage.objects;
create policy "private document objects update" on storage.objects
  for update using (
    bucket_id = 'permitpilot-documents'
    and split_part(name, '/', 1) = auth.uid()::text
  ) with check (
    bucket_id = 'permitpilot-documents'
    and split_part(name, '/', 1) = auth.uid()::text
  );

drop policy if exists "private document objects delete" on storage.objects;
create policy "private document objects delete" on storage.objects
  for delete using (
    bucket_id = 'permitpilot-documents'
    and split_part(name, '/', 1) = auth.uid()::text
  );
