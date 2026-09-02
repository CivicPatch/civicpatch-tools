# Database Schema

> **This is the authoritative schema reference.** Keep this diagram in sync with migrations. Whenever a migration adds, renames, or drops a column, table, or index, update the chart below.
>
> Types suffixed `_null` (e.g. `text_null`) are nullable. All others are NOT NULL.

```mermaid
erDiagram
    %% idx = regular index, functional idx noted inline
    users {
        uuid            id              PK
        text            provider        "unique: (provider, provider_user_id)"
        text            provider_user_id
        text            email
        text_null       display_name    "unique (NULLs distinct)"
        text            role            "default: 'default', CHECK IN ('default','contributors','maintainers','admins')"
        timestamptz_null last_login_at  "set by upsert_user on every successful sign-in"
        timestamptz_null created_at
    }

    jurisdictions {
        text            jurisdiction_ocdid  PK
        text            status              "check: active|inactive, default: active. inactive = removed from the synced jurisdictions.yml upstream; derived from presence in the file, never read out of it"
        text_null       state               "idx"
        text            level               "idx, default: 'local'"
        jsonb_null      data                "idx: (data->>'geoid'), LOWER(data->>'name')"
        text            search_text         "idx: GIN to_tsvector('simple',_), GIN gin_trgm_ops; default: ''; name+display_name+state code+state name, maintained by sync"
        text_array      parent_ocdids       "idx: GIN; default: '{}'; ancestry most-specific-first, incl. the implied state; maintained by sync"
        timestamptz_null scraped_at          "idx: (state, scraped_at); last *scraped*, stamped on job-PR merge"
        timestamptz_null updated_at
    }

    synced_files {
        text            path                PK
        text            blob_sha            "last-synced git blob SHA (sync cursor); data_source/** only"
        timestamptz     synced_at           "default: now()"
    }

    changesets {
        uuid            id                  PK
        text            kind                "CHECK scrape|sheet_import|people_edit|jurisdiction_edit; CHECK (kind=scrape) = (status IS NOT NULL)"
        text_null       jurisdiction_ocdid  FK  "idx"
        uuid_null       created_by_user_id FK
        jsonb           arguments_json
        timestamptz_null published_at       "set when a reviewer approves; this is the publish state"
        timestamptz_null dismissed_at       "set when a reviewer rejects. check: not both set"
        uuid_null       resolved_by_user_id FK  "whoever published or dismissed it"
        text_null       change_url          "where the change landed: a commit URL going forward, a PR URL on backfilled rows"
        text_null       status              "147: was pipeline_runs.status. null when no pipeline ran"
        int_null        progress            "147: was pipeline_runs.progress"
        timestamptz_null sourced_at         "147: when the run last read the source; dates last_seen_at, and orders supersede"
        timestamptz     created_at
        uuid_null       batch_id            FK  "idx. NULL for every changeset made outside a batch, which is most"
    }

    changeset_batches {
        uuid            id                  PK
        text            kind                "CHECK sheet_import|scrape — same vocabulary as changesets.kind"
        text            lock_key            "idx: (lock_key, started_at DESC). 'sheet:<id>' | 'state:wa' — what this run must not race"
        jsonb           arguments_json      "producer-specific inputs: the spreadsheet, or the state and how many"
        text            status              "CHECK running|succeeded|failed|abandoned. lifecycle only, never progress"
        int_null        items_total         "how many the run will attempt. progress is count(changesets WHERE batch_id) out of this — the changesets are the items, so no counter and no result blob"
        text_null       error
        uuid            started_by_user_id  FK
        timestamptz     started_at
        timestamptz_null finished_at        "UNIQUE (lock_key) WHERE finished_at IS NULL — the lock, one running batch per target"
    }

    people {
        uuid            id                  PK
        text            jurisdiction_ocdid  FK  "idx"
        jsonb           data                "134: being retired into the columns below; still authoritative until every reader moves"
        text_null       name                "134: nullable only during the transition; NOT NULL arrives with the contract migration"
        text_array      other_names         "134"
        text_array      phones              "134"
        text_array      emails              "134"
        text_array      urls                "134"
        text_array      source_urls         "134"
        text_null       image               "134"
        text_null       cdn_image           "134"
        timestamptz_null updated_at         "from the record's own updated_at — data, not a publish time" 
    }

    issues {
        uuid            id          PK
        text            issue_type      "idx"
        text            issue_key       "unique: (issue_type, issue_key)"
        text_array      changeset_ids
        jsonb           data
        text            status          "idx, check: pending|pr_opened|resolved|superseded"
        text_null       pull_request_url
        timestamptz_null resolved_at
        timestamptz     created_at
        boolean         is_flagged      "default: false"
    }

    review_sessions {
        uuid            id                      PK
        uuid            user_id                 FK
        text            state_code              "idx: unique (user_id, state_code) WHERE ended_at IS NULL"
        int             daily_goal
        int             current_entry_number    "default: 1"
        timestamptz     updated_at              "default: NOW()"
        timestamptz_null ended_at
        timestamptz_null created_at
    }

    review_session_entries {
        uuid            id                  PK
        uuid            review_session_id   FK  "idx: (review_session_id, status, created_at DESC)"
        text_array      changeset_ids
        text            jurisdiction_ocdid      "idx: unique WHERE status = 'claimed'"
        text            status
        int_null        entry_number
        timestamptz_null created_at
        timestamptz_null resolved_at
    }

    api_keys {
        int             id              PK
        uuid            user_id         FK  "idx"
        text            api_key_suffix
        text            api_key_hash        "idx"
        timestamptz_null created_at      "default: now()"
        timestamptz_null revoked_at      "idx"
    }

    api_usage_limits {
        int             id          PK
        uuid            user_id     FK  "unique"
        int             daily_limit
    }

    change_log_types {
        text            type                PK
    }

    change_logs {
        uuid            id                  PK
        text            type                FK  "references change_log_types(type)"
        text_null       jurisdiction_ocdid  "idx"
        text_null       changeset_id        "the changeset the change belongs to; NULL for non-review changes"
        jsonb_null      changes             "type-specific payload; {field,from,to} diff for edit_person"
        uuid_null       user_id             FK
        timestamptz     created_at          "idx: created_at DESC, default: now()"
    }

    source_records {
        uuid            id                  PK
        uuid            changeset_id        FK  "idx; ON DELETE CASCADE — which scrape"
        text            jurisdiction_ocdid  FK  "idx"
        text            name                "verbatim, as the page spelled it"
        text            label               "idx; verbatim. ONE RECORD PER LABEL is the contract with the pipeline — a person seen under two titles is two rows"
        text            source_url          "the page this sighting came from"
        text_null       url                 "the person's own link"
        text_null       phone
        text_null       email
        text_null       image               "where the photo came from; named as on people"
        text_null       cdn_image           "where we put it (R2). Stored, not composed from a template — where a file lives is a fact"
        text_null       start_date          "text, not date: sources give partial dates (2024, 2024-01)"
        text_null       end_date
        timestamptz     created_at          "default: now()"
    }

    source_record_identities {
        uuid            source_record_id    PK, FK "ON DELETE CASCADE"
        uuid            person_id           "144: uuid, not text — as text it accepted the ambiguous-match sentinel and the card reached the pool with a broken cluster id. No FK: ids are minted at ingest, the people row arrives at publish. idx; SEPARATE FROM THE EVIDENCE deliberately — linkage is not a fact about a page and is not stable across runs (#2480), so re-linking rewrites this table and never touches a record"
        timestamptz     resolved_at         "default: now()"
    }

    roles {
        text            id                  PK "SLUG, not a uuid: council-member. Immune to label renames. check: id <> ''"
        text            label               "unique idx: (lower(label)); display name, renameable"
        text            status              "check: active|candidate|excluded|inactive"
        bool            is_unique           "default: false"
        int_null        priority            "NULL = unranked, sorts last"
        timestamptz     created_at
    }

    role_aliases {
        uuid            id                  PK
        text            role_id             FK  "idx; ON UPDATE CASCADE, ON DELETE CASCADE"
        text            label               "unique idx: (lower(label)) — across ALL roles"
        text            status              "check: active|candidate, default: candidate"
        timestamptz     created_at
    }

    organizations {
        uuid            id                  PK
        text            jurisdiction_ocdid  FK  "unique: (jurisdiction_ocdid, name)"
        text            name                "one body — City Council, Township Board. Derivation currently mints one per jurisdiction"
        int             sort_order          "default: 0"
        timestamptz     created_at          "default: now()"
    }

    divisions {
        text            ocdid               PK "ocd-division/...; minted lazily when a post needs it"
        text            jurisdiction_ocdid  FK
        timestamptz     created_at          "default: now()"
    }

    posts {
        uuid            id                  PK "also unique (id, organization_id) so memberships can FK the pair — kept: that column feeds a partial unique index and its failure would be silent"
        text            jurisdiction_ocdid  FK "denormalised for direct queries; 121 dropped the composite FK — a mismatch is visible, not silent"
        uuid            organization_id     FK
        text            role_id             FK "ON UPDATE CASCADE; the POST's own role — other roles the label named live in membership_roles"
        text            division_ocdid      FK "ON UPDATE CASCADE"
        int             _headcount          "check: > 0, default: 1; human-owned. Underscored: Popolo has no headcount — our Post is a group of interchangeable seats"
        bool            _is_tracked         "default: true; a roster omitting this post is meaningful — gates the review queue, not the record. Orthogonal to lifecycle"
        timestamptz     created_at          "default: now()"
    }

    memberships {
        uuid            id                  PK
        uuid            post_id             FK "composite FK (post_id, organization_id) ON UPDATE CASCADE"
        uuid            organization_id     "unique idx: (person_id, organization_id) WHERE closed_at IS NULL — one open post per body"
        uuid            person_id           FK
        text_array      designations        "default: {}; how the source tells one post from another: Place 2, Position 8"
        text_array      unmatched_text      "gin idx; default: {}; parts that produced NO role. Residue from a part that DID resolve rides on label instead — it is not unclassifiable and no rule fixes it"
        text_array      source_labels       "default: {}; what the SOURCE called this post, split — parsed.labels, i.e. office.name broken on ' - '. Parts not the rendering, so triage can show the one label a term came from. No FK to source_records: a membership outlives its evidence, and writing this beside unmatched_text is what stops the two disagreeing"
        text_null       label               "the source's words for what the post label cannot say — seeded on INSERT, then human-owned. Absent from upsert()'s ON CONFLICT SET, which is its whole protection. NULL = the post says it all"
        text_null       start_date          "144: text, not date — sources give partial dates and Popolo allows them (3,513 of 4,547 on dev are partial). From the source; we do not infer it"
        text_null       end_date            "144: text, as start_date. From the source — NOT set when someone stops appearing"
        timestamptz     first_seen_at       "when the SOURCE said it, not when the row was written"
        timestamptz     last_seen_at        "advanced on every scrape that still lists them"
        timestamptz_null closed_at          "set when a scrape stops listing them; NULL = currently open"
        timestamptz     created_at          "default: now()"
    }

    membership_roles {
        uuid            membership_id       FK "PK (membership_id, role_id); ON DELETE CASCADE"
        text            role_id             FK "PK; idx; ON UPDATE CASCADE — renaming a role follows into closed history"
    }

    assertions {
        uuid            id                  PK
        text            entity_type         "CHECK post|membership|person; no FK — heterogeneous subjects, the price of an event log"
        uuid            entity_id           "no FK; deletes are refused rather than cascaded"
        text_null       field_path          "NULL = the entity itself, not a field. UNIQUE NULLS NOT DISTINCT, so no sentinel"
        text            kind                "CHECK confirm|correct|retract"
        jsonb_null      value               "corrections only; NULL = deliberately empty, which is why kind exists"
        jsonb_null      sources             "[{note, url}] — note may stand alone: 'phoned the clerk'"
        uuid            asserted_by         FK "NOT NULL — an assertion nobody made is not an assertion"
        timestamptz     asserted_at         "idx: (entity_type, entity_id, asserted_at DESC). APPEND-ONLY — history is only trustworthy if rows never change"
    }

    roles ||--o{ role_aliases : "role_id"
    jurisdictions ||--o{ organizations : "jurisdiction_ocdid"
    jurisdictions ||--o{ divisions : "jurisdiction_ocdid"
    jurisdictions ||--o{ posts : "jurisdiction_ocdid"
    organizations ||--o{ posts : "organization_id"
    roles ||--o{ posts : "role_id"
    divisions ||--o{ posts : "division_ocdid"
    posts ||--o{ memberships : "post_id"
    people ||--o{ memberships : "person_id"
    roles ||--o{ membership_roles : "role_id"
    memberships ||--o{ membership_roles : "membership_id"
    users ||--o{ assertions : "asserted_by"
    users ||--o{ changeset_batches : "started_by_user_id"
    changeset_batches ||--o{ changesets : "batch_id"
    changesets ||--o{ source_records : "changeset_id"
    jurisdictions ||--o{ source_records : "jurisdiction_ocdid"
    source_records ||--o| source_record_identities : "source_record_id"
    jurisdictions ||--o{ changesets : "jurisdiction_ocdid"
    jurisdictions ||--o{ people : "jurisdiction_ocdid"
    changesets }o--o{ issues : "changeset_ids"
    users ||--o{ review_sessions : "user_id"
    users ||--o{ changesets : "created_by_user_id"
    users ||--o{ api_keys : "user_id (ON DELETE CASCADE)"
    users ||--o| api_usage_limits : "user_id (ON DELETE CASCADE)"
    change_log_types ||--o{ change_logs : "type"
    users ||--o{ change_logs : "user_id (ON DELETE SET NULL)"
    jurisdictions ||--o{ change_logs : "jurisdiction_ocdid"
    roles ||--o{ change_logs : "jurisdiction_ocdid"
    review_sessions ||--o{ review_session_entries : "review_session_id"
```

**Notes:**
- `jurisdictions.data` — jurisdiction metadata (name, geoid, etc.)
- `pipeline_runs` was folded into `requests` in migration 147: `changeset_id` was UNIQUE NOT NULL and every request had exactly one run, so the two tables were a vertical partition of one entity that 21 queries had to join. `pull_requests` went the same way in 141 — nothing opens a pull request for a scrape any more, and every column it held either lived on `requests` already or died with the merge queue.
- **`requests` became `changesets` in migration 152**, with `request_batches` → `changeset_batches`, `source_records.request_id` → `changeset_id`, and `change_logs.request_id` → `changeset_id`. Pure rename, including every index and constraint name — a rename that leaves `requests_pkey` on `changesets` puts the old vocabulary back into the schema in a dozen places. The table grew from "a job someone asked for" and that fits only the oldest of its four producers: nobody *requests* a sheet import, and both hand-edit kinds are born published. What all four are is a bundle of proposed changes to one jurisdiction, by one producer, at one time, awaiting a decision. `submissions` was rejected as past tense — it misnames the whole dispatched-and-running phase of a scrape, which exists at `status = PENDING, progress = 0` before it has any `source_records`, exactly the state an OSM changeset models as open-and-empty. **Migration 156 finished the job**: `issues.request_ids` and `review_session_entries.request_ids` — plural arrays 152 did not touch — became `changeset_ids`, and `requested_by_user_id` became `created_by_user_id`, matching its neighbour `resolved_by_user_id` and `changeset_batches.started_by_user_id`. It stays nullable, and the null is load-bearing: a changeset with no user was machine-triggered. `issues.pull_request_url` keeps its name — it is a genuine GitHub pull request.
- **`open_data_url` became `change_url` in migration 157.** The column always held a commit url *or* a PR url, so the old name said which repo the thing was in rather than what it is; both are "the change". It stutters as `changesets.change_url`, accepted deliberately — the entity is a changeset and so is what the url points at, so there is no second noun to learn.
- **`request_type` became `kind` in migration 153**, and started saying *which producer made this changeset* rather than which domain object it was about. Every row used to read `people`, leaving three producers told apart by a conjunction of `status IS NULL` and `batch_id IS NOT NULL` — neither of which is about provenance. Two CHECKs now hold what nothing enforced: the four-value vocabulary, and `(kind = 'scrape') = (status IS NOT NULL)`, which makes the nullable pipeline columns a *consequence* of the kind instead of the only way to guess it. **The default was dropped deliberately** — a writer that does not say which producer it is should fail, not quietly become a scrape. `changeset_batches.kind` lost its `state_` prefix in the same migration so both columns share one vocabulary, which is what lets the backfill read the batch's own answer rather than infer from `batch_id IS NOT NULL` — a rule that holds only while state scrapes create no batch rows. `jurisdiction_edit` is a kind here only until those edits move to their own table; see the ▶ Next entry in `.scratch/TODO.md`.
- `people` has no FK to `changesets` — it is written by the publish transaction, not by a merge
- `state_configs` was **dropped in migration 150**, along with `sync_log` (superseded by `synced_files` and untouched since migration 003) and `logs` (0 rows, no reader; application logs go to Grafana). 103 had dropped `state_configs.min_scraped_at` when freshness became a computed rolling window and kept the shell as the home for the next per-state setting; two months on it held none, had no reader, and `jurisdictions.state` already answered which states exist. Bringing it back is one statement if a per-state setting ever arrives.
- `publish_timestamp_backup_117` was **dropped in migration 151**, on the judgement that 117 is permanent. It was never in this diagram — it was 117's snapshot of the `published_at` / `dismissed_at` / `resolved_by_user_id` values it re-stamped, kept because they cannot be recomputed (115 stored `pr.updated_at` as it stood then, and pr_sync rewrote that column on every reconciliation). **151 is deliberately irreversible**: its down is a no-op rather than an empty recreation, because 117's down is an `UPDATE … FROM` that against an empty table would update zero rows and report success — silently leaving the re-stamped values in place while appearing to restore them. Note 117's up could not be replayed anyway: it reads `pull_requests`, dropped in 141.
- `roles` replaced `role_terms` / `role_aliases` in migration 106, and migration 109 **flattened it**: the `scope` column (NULL=global / state ocdid / place ocdid) is gone, along with per-scope resolution, alias unioning, and the `roles_global_complete` check. It carried 24 global rows and 1 scoped test row while costing the promotion trap — promoting a role was DELETE + INSERT, minting a new uuid and breaking any FK pointing at it. One flat list, `unique (lower(label))`. #2470 and #2471 ask for *more* hierarchy and are inverted by this; see `.scratch/2026-08-12-plan-flat-roles.md`.
- **`roles.id` is a slug, not a uuid** — `council-member`, derived from `label` at creation. Migration 109 swapped the uuid for it. Read that carefully: `id` is a uuid in every other domain table, and this schema's other text-PK tables name the column for its content (`geoid`, `path`, `type`), so `roles.id` matches neither convention. It is named `id` so Phase 2's FK reads `posts.role_id` rather than `posts.role_slug`.
- The consequence of that choice: unlike a uuid, this id is *derived*, so it can be **wrong**. Mint "Concil Member", fix the label to "Council Member", and the id stays `concil-member` — a rename moves `label` and deliberately leaves `id`, which is what keeps published references resolving. Phase 2's `posts.role_id` should use `ON UPDATE CASCADE` so correcting a mis-derived id stays one statement.
- `core.role_taxonomy.slugify_label` must reproduce migration 109's backfill expression exactly (`trim(both '-' from lower(regexp_replace(label, '[^a-zA-Z0-9]+', '-', 'g')))`), or a role minted by the app and one minted by the migration would disagree.
- **Slugging is lossy, so the PK is a stricter constraint than `unique (lower(label))`.** Same lowercase label ⟹ same slug, but not the reverse: `Council/Member` and `Council Member` are two distinct labels that reduce to one id. The label index therefore catches nothing the PK doesn't — it is kept as documentation of intent, not for coverage. `core.role_taxonomy.slug_conflict_error` rejects such a pair before the write so the message can name both labels; the PK is the concurrency backstop.
- `roles_id_not_empty` exists because `NOT NULL` does not cover `''`: a label of pure punctuation slugs to the empty string, which would otherwise insert silently as published identity. `schemas.roles.RoleInput` rejects such a label at the API boundary; the check covers any other writer.
- **Labels and aliases share one case-insensitive namespace, and no index can enforce it.** `roles_label_lower_uq` spans `roles`, `role_aliases_label_lower_uq` spans `role_aliases`, and a unique index cannot span both — so nothing at the schema level stops one role claiming another's *label* as an alias. That matters because `get_role_alias_map` lets the last role written win, making the owner depend on priority order (a reorder could silently flip it). `core.role_taxonomy.name_conflict_error` enforces the cross-table half before the write. A role restating *its own* label as an alias is allowed: it resolves to itself, and seeded rows do it (`Select Board Member`, `Deputy Mayor Pro Tempore`).
- `roles.status`: each value is a distinct matcher behaviour — `active` matches; `candidate` matches and flags for #2471's triage; `excluded` matches so the label can be *knowingly dropped* (an exclusion like `Webmaster`, dormant since `/config/exclude` and `/config/include` were removed); `inactive` is not matched at all, and is what removal sets, so the row and any seat history survive. `active` is the only value in use today. **`shared.utils.config_utils.get_role_configs` filters to `active` and is the only reader** — before it, `status` had zero readers, which was not harmless: an `excluded` role was matched as an ordinary one. The filter is blunter than the design above, though: it makes `excluded` invisible rather than match-then-drop, so an excluded label falls through to `unrecognized_role`. The vocabulary went `kind: canonical|exclusion` → `status: …|rejected` → `status: …|excluded`; the last step realigns it with the `exclude_role` / `include_role` change-log types, which are permanent because existing `change_logs` rows FK to them.
- `role_aliases` was a `roles.aliases text[]` between migrations 106 and 110. The array could not express either thing the table exists for: a per-alias approval state (an alias must not match until approved), and uniqueness *across* roles — nothing stopped one string aliasing two roles, which makes the matcher's answer arbitrary. `role_aliases_label_lower_uq` is deliberately global, not per-role.
- `role_aliases.status` defaults to `candidate`, but every alias written through `PUT /api/v1/roles` is set `active`: a maintainer typing one *is* the approval. The default is aimed at a future auto-mint path, which is the case approval was designed for. `get_roles` returns only `active` aliases, so the wire shape stays `aliases: ["…"]` and the pipeline cannot accidentally match an unapproved one.
- `roles.priority` stays nullable on purpose: `ORDER BY priority NULLS LAST` treats NULL as a real state (unranked, sorts to the end), which `NOT NULL DEFAULT 0` would collapse into "ranked first". **`PUT /api/v1/roles/reorder` is its only writer**, and it keys on `id`; `RoleInput` deliberately has no `priority` field. Two reasons: reorder is ADMINS-only while the upsert is MAINTAINERS, so accepting it on the upsert would bypass that gate — and an omitted field would read as "clear it", which flattened every role's ordering on any save.
- `synced_files` is keyed by repo path (e.g. `data_source/tx/local/jurisdictions.yml`) — no FK; it holds the last-synced git blob SHA per file the open-data sync tree-diffs. **`data_source/**` only.** Migration 150 deleted 3,430 `data/**` (people) cursors and `get_current_tree`/`get_stored_tree` stopped computing them: people files are rendered *from* the database and overwritten on every publish, so a cursor over them describes a direction that no longer exists — and got staler with every write. The sync is one-way per path: `data_source/**` flows open-data → DB, `data/**` flows DB → open-data.
- `jurisdictions.scraped_at` is "last *scraped*" — stamped on job-PR merge, **not** bumped by manual people edits (so hand-corrected jurisdictions don't read as freshly scraped)
- `users.provider` + `users.provider_user_id` form a unique constraint; `id` is the actual primary key
- `users.role` is a single trust level per user (one of `default`, `contributors`, `maintainers`, `admins`); permissions cascade downward (admin implies maintainer implies contributor implies default). The `user_roles` join table was dropped in migration 087.
- `api_keys`, `api_usage_limits` use `user_id` (UUID FK to `users.id`); the deprecated composite `(provider, provider_user_id)` shape was migrated out in migration 086.
