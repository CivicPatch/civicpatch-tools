# Database Schema

> **This is the authoritative schema reference.** Keep this diagram in sync with migrations. Whenever a migration adds, renames, or drops a column, table, or index, update the chart below.

```mermaid
erDiagram
    %% idx = regular index, functional idx noted inline
    users {
        uuid id PK
        text provider "unique: (provider, provider_user_id)"
        text provider_user_id
        text email
        text display_name
        text server_url
        bool is_approved
        timestamptz created_at
    }

    jurisdictions {
        text jurisdiction_ocdid PK
        text state
        text status
        jsonb data "idx: (data->>'geoid'), LOWER(data->>'name')"
        timestamp updated_at
    }

    requests {
        uuid id PK
        text request_type
        text jurisdiction_ocdid FK
        uuid requested_by_user_id FK
        jsonb arguments_json
        jsonb result_data
        jsonb review_json "idx: jsonb_array_length(review_json->'issues')"
        timestamptz created_at
        timestamptz updated_at
    }

    jobs {
        int id PK
        uuid request_id FK "idx"
        text requested_by_provider "idx: (requested_by_provider, requested_by_provider_user_id)"
        text requested_by_provider_user_id
        int progress
        text status "idx"
        bigint github_run_id
        timestamptz created_at
        timestamptz updated_at
    }

    pull_requests {
        uuid id PK
        uuid request_id FK
        uuid resolved_by_user_id FK
        int pr_number
        text url
        text status
        text review_state
        timestamptz merged_at
        timestamptz created_at
        timestamptz updated_at
    }

    people {
        uuid id PK
        text jurisdiction_ocdid FK
        jsonb data
        text status
        timestamptz updated_at
    }

    notes {
        uuid id PK
        text jurisdiction_ocdid FK "idx"
        text body
        text user_id
        timestamptz created_at
    }

    job_events {
        uuid id PK
        uuid request_id FK "idx"
        text event_type "idx"
        jsonb data
        timestamptz created_at
    }

    review_sessions {
        uuid id PK
        uuid user_id FK
        text state_code
        int daily_goal
        timestamptz created_at
    }

    review_session_entries {
        uuid id PK
        uuid review_session_id FK "idx: (review_session_id, status, created_at DESC)"
        text request_id
        text jurisdiction_ocdid
        text status
        int entry_number
        timestamptz created_at
        timestamptz resolved_at
    }

    jurisdictions ||--o{ requests : "jurisdiction_ocdid"
    jurisdictions ||--o{ people : "jurisdiction_ocdid"
    jurisdictions ||--o{ notes : "jurisdiction_ocdid"
    requests ||--o| jobs : "request_id"
    requests ||--o| pull_requests : "request_id"
    requests ||--o{ job_events : "request_id"
    users ||--o{ review_sessions : "user_id"
    users ||--o{ requests : "requested_by_user_id"
    users ||--o{ pull_requests : "resolved_by_user_id"
    review_sessions ||--o{ review_session_entries : "review_session_id"
```

**Notes:**
- `requests.result_data` — array of scraped `Official` objects returned by the civicpatch pipeline
- `requests.review_json` — pipeline review output (`issues`, `warnings`, etc.)
- `people.data` — full `Official` JSONB blob; the canonical record for a jurisdiction's current officials
- `jurisdictions.data` — jurisdiction metadata (name, geoid, etc.)
- `jobs` and `pull_requests` each have a unique constraint on `request_id` (one-to-one with `requests`)
- `people` has no FK to `requests` — it is updated independently when a PR is merged
- `users.provider` + `users.provider_user_id` form a unique constraint; `id` is the actual primary key
