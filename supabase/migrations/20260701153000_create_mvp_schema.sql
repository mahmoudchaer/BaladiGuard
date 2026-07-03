create extension if not exists pgcrypto;

create type user_role as enum (
  'citizen',
  'municipality_admin'
);

create type report_priority as enum (
  'low',
  'medium',
  'high'
);

create type report_status as enum (
  'submitted',
  'under_review',
  'assigned',
  'in_progress',
  'resolved'
);

create table municipalities (
  id uuid primary key default gen_random_uuid(),
  name varchar not null,
  city varchar not null,
  governorate varchar not null,
  created_at timestamp with time zone not null default now()
);

create table departments (
  id uuid primary key default gen_random_uuid(),
  municipality_id uuid not null references municipalities(id) on delete cascade,
  name varchar not null,
  description text
);

create table users (
  id uuid primary key default gen_random_uuid(),
  municipality_id uuid references municipalities(id) on delete set null,
  phone varchar not null unique,
  full_name varchar,
  role user_role not null default 'citizen',
  reputation_score integer not null default 0,
  created_at timestamp with time zone not null default now()
);

create table duplicate_groups (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone not null default now()
);

create table reports (
  id uuid primary key default gen_random_uuid(),
  created_by uuid not null references users(id) on delete restrict,
  municipality_id uuid not null references municipalities(id) on delete cascade,
  department_id uuid references departments(id) on delete set null,
  duplicate_group_id uuid references duplicate_groups(id) on delete set null,
  description text not null,
  latitude decimal(10, 8) not null,
  longitude decimal(11, 8) not null,
  address text,
  category varchar not null,
  priority report_priority not null default 'medium',
  status report_status not null default 'submitted',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table images (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references reports(id) on delete cascade,
  storage_key varchar not null,
  created_at timestamp with time zone not null default now()
);

create table status_history (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references reports(id) on delete cascade,
  previous_status report_status,
  new_status report_status not null,
  updated_by uuid not null references users(id) on delete restrict,
  note text,
  created_at timestamp with time zone not null default now()
);

create table ai_outputs (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null unique references reports(id) on delete cascade,
  cleaned_description text,
  predicted_category varchar,
  confidence double precision,
  urgency_score integer,
  urgency_reason text,
  suggested_department_id uuid references departments(id) on delete set null,
  summary text,
  created_at timestamp with time zone not null default now(),
  constraint ai_outputs_confidence_range check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  ),
  constraint ai_outputs_urgency_score_range check (
    urgency_score is null or (urgency_score >= 0 and urgency_score <= 100)
  )
);

create index departments_municipality_id_idx on departments(municipality_id);
create index users_municipality_id_idx on users(municipality_id);
create index reports_created_by_idx on reports(created_by);
create index reports_municipality_id_idx on reports(municipality_id);
create index reports_department_id_idx on reports(department_id);
create index reports_duplicate_group_id_idx on reports(duplicate_group_id);
create index reports_status_idx on reports(status);
create index reports_priority_idx on reports(priority);
create index reports_created_at_idx on reports(created_at);
create index images_report_id_idx on images(report_id);
create index status_history_report_id_idx on status_history(report_id);
