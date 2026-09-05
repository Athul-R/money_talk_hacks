-- Explain the Change — FP&A lineage schema. Apply once: psql $DB_URL -f data/schema.sql
-- Mirrors the Rock Scheduler Shift/Offer/EventRow shape: a run is the contested
-- row, branches are the scoreboard, events are the append-only audit the UI
-- replays as beats. The engine writes rows as it works; the console only reads.

-- One row per company the agent analyzes. Ontology = dimensions.json compiled;
-- thresholds = materiality knobs (data, not code).
create table companies (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    ontology jsonb not null default '{}',
    thresholds jsonb not null default '{}',
    created_at timestamptz not null default now()
);

-- One row per uploaded bundle (summaries + transactions + dims + optional kpis).
create table datasets (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id),
    name text not null,
    summary_path text not null,
    txn_path text not null,
    dims_path text not null,
    periods text[] not null default '{}',
    uploaded_at timestamptz not null default now()
);

-- One analysis: metric + period pair. beat is the engine's clock; the console
-- scrubber replays events grouped by payload->>'beat'.
create table runs (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id),
    dataset_id uuid not null references datasets(id),
    metric text not null,
    period_a text not null,
    period_b text not null,
    -- queued | running | complete | failed
    status text not null default 'queued',
    beat int not null default 0,
    summary_md text,
    created_at timestamptz not null default now()
);

-- One lane in the lineage graph. lane is assigned once at spawn (append-only,
-- the graph never re-sorts); depth indents child groups under a drilled parent.
-- evidence is the full evidence object (§4 of the spec), children nested by id.
create table branches (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs(id),
    parent_branch_id uuid references branches(id),
    depth int not null default 0,
    dimension text not null,          -- product | geography | user_type | customer | line_item
    name text not null,
    lane int not null,
    value_a double precision not null,
    value_b double precision not null,
    delta_abs double precision not null,
    delta_pct double precision,
    share double precision not null,  -- share of parent variance, signed
    zscore double precision,
    -- active | done | capped
    state text not null default 'active',
    evidence jsonb not null default '{}'
);

-- One stage node in a branch's pip chain.
create table pips (
    id uuid primary key default gen_random_uuid(),
    branch_id uuid not null references branches(id),
    stage text not null,              -- delta_z | drivers | cluster | drill | explain | ask
    stage_idx int not null,
    -- waiting | active | done | capped
    state text not null default 'waiting',
    payload jsonb not null default '{}',
    at timestamptz not null default now()
);

-- Append-only audit; every row is one beat fragment the console can fold.
-- kinds: run_started, axis_selected, branch_ranked, zscore_flagged,
--        attribution_done, cluster_found, concentration_flagged, drill_spawned,
--        branch_capped, memory_recalled, memory_learned, explanation_ready,
--        run_complete
create table events (
    id bigint generated always as identity primary key,
    run_id uuid not null references runs(id),
    branch_id uuid references branches(id),
    kind text not null,
    payload jsonb not null default '{}',
    at timestamptz not null default now()
);

-- Persistent company memory. The LLM may compile free text into these rows at
-- WRITE time; the engine reads only plain rows at run time (no model call in
-- the attribution loop). kinds: seasonality | normal_range | recurring_driver |
-- concentration | known_event | anomaly | explanation
create table memory (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id),
    kind text not null,
    key text not null,
    value jsonb not null default '{}',
    evidence_run_ids uuid[] not null default '{}',
    updated_at timestamptz not null default now(),
    unique (company_id, kind, key)
);

-- The whole index budget.
create index runs_company_idx on runs (company_id, created_at desc);
create index branches_run_idx on branches (run_id, lane);
create index pips_branch_idx on pips (branch_id, stage_idx);
create index events_run_idx on events (run_id, id);
create index memory_company_idx on memory (company_id, kind);

-- The console never polls: realtime on the four hot tables.
alter publication supabase_realtime add table runs;
alter publication supabase_realtime add table branches;
alter publication supabase_realtime add table pips;
alter publication supabase_realtime add table events;

-- App writes via service role only. RLS on with read-only anon policies:
-- the console is a pure window, the engine is the only writer.
alter table companies enable row level security;
alter table datasets enable row level security;
alter table runs enable row level security;
alter table branches enable row level security;
alter table pips enable row level security;
alter table events enable row level security;
alter table memory enable row level security;

create policy read_companies on companies for select using (true);
create policy read_datasets on datasets for select using (true);
create policy read_runs on runs for select using (true);
create policy read_branches on branches for select using (true);
create policy read_pips on pips for select using (true);
create policy read_events on events for select using (true);
create policy read_memory on memory for select using (true);
