# MVP Database Schema

The MVP database contains eight core tables for municipalities, users, complaint reports, report media, status tracking, AI processing output, and duplicate grouping.

## 1. Municipalities

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| name | VARCHAR | Municipality name |
| city | VARCHAR | City |
| governorate | VARCHAR | Governorate |
| created_at | TIMESTAMP | Creation timestamp |

## 2. Departments

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| municipality_id | UUID | FK to Municipalities |
| name | VARCHAR | Department name |
| description | TEXT | Department responsibilities |

## 3. Users

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| municipality_id | UUID, nullable | FK to Municipalities |
| phone | VARCHAR | Unique phone number |
| full_name | VARCHAR | Optional full name |
| role | ENUM | `citizen`, `municipality_admin` |
| reputation_score | INTEGER | Trust score |
| created_at | TIMESTAMP | Creation timestamp |

## 4. Reports

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| created_by | UUID | FK to Users |
| municipality_id | UUID | FK to Municipalities |
| department_id | UUID, nullable | FK to Departments |
| duplicate_group_id | UUID, nullable | FK to DuplicateGroups |
| description | TEXT | User description |
| latitude | DECIMAL | GPS latitude |
| longitude | DECIMAL | GPS longitude |
| address | TEXT | Human-readable address |
| category | VARCHAR | Report category, such as road or waste |
| priority | ENUM | `low`, `medium`, `high` |
| status | ENUM | `submitted`, `under_review`, `assigned`, `in_progress`, `resolved` |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

## 5. Images

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| report_id | UUID | FK to Reports |
| storage_key | VARCHAR | S3 or Supabase storage path |
| created_at | TIMESTAMP | Upload timestamp |

## 6. StatusHistory

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| report_id | UUID | FK to Reports |
| previous_status | ENUM | Previous report status |
| new_status | ENUM | New report status |
| updated_by | UUID | FK to Users |
| note | TEXT | Optional note |
| created_at | TIMESTAMP | Timestamp |

## 7. AIOutputs

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| report_id | UUID | FK to Reports |
| cleaned_description | TEXT | AI-cleaned description |
| predicted_category | VARCHAR | AI prediction |
| confidence | FLOAT | Confidence score |
| urgency_score | INTEGER | 0-100 urgency score |
| urgency_reason | TEXT | Explanation |
| suggested_department_id | UUID | FK to Departments |
| summary | TEXT | AI-generated summary |
| created_at | TIMESTAMP | Timestamp |

## 8. DuplicateGroups

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| created_at | TIMESTAMP | Creation timestamp |

## Relationships

```text
Municipality (1)
├── Departments (N)
├── Users (N)
└── Reports (N)

Department (1)
└── Reports (N)

User (1)
└── Reports (N)

Report (1)
├── Images (N)
├── StatusHistory (N)
├── AIOutput (1)
└── DuplicateGroup (N:1)
```

## Future Consideration

The `ai_outputs` table may later be merged into `reports` if the project only stores a small amount of AI metadata.
