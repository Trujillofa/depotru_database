-- DRAFT ONLY (superseded reference). Not registered with any migration runner.
-- NEVER APPLIED. The REAL, owner-reviewable migration now lives in the
-- depotru-inbox repo as a numbered sql/ migration; this file remains an inert
-- design reference only. Deliberately aborts before DDL even if executed.
BEGIN;
DO $$ BEGIN RAISE EXCEPTION 'DRAFT WCX import is not approved'; END $$;

-- Owner decisions applied (2026-11-21):
--   * No contact_id / link_state / manual approval flow. History joins inbox
--     contacts IN READ ONLY by normalized phone_e164. Shared phones
--     (multiple source customers) are flagged phone_shared and never merged.
--   * wcx_cases.raw keeps the complete original envelope JSON, including the
--     1,154 movement entries without a positive source ID.
--   * Timezone is America/Bogota (owner-confirmed).
--   * Actor mapping: isAutomation -> automation; isAdmin/agent -> agent;
--     everything else -> customer. Raw flags are preserved as booleans.
--   * Retention: keep everything (owner rule). No deletion or TTL anywhere.

CREATE TABLE wcx_customers (
    source text NOT NULL CHECK (source ~ '^[a-z0-9_-]{1,64}$'),
    source_customer_id bigint NOT NULL CHECK (source_customer_id > 0),
    phone_e164 text CHECK (phone_e164 ~ '^\+57(3[0-9]{9}|60[1245678][0-9]{7})$'),
    phone_shared boolean NOT NULL DEFAULT false,
    display_name text,
    source_fingerprint bytea NOT NULL CHECK (octet_length(source_fingerprint) = 32),
    first_batch_sha256 bytea NOT NULL CHECK (octet_length(first_batch_sha256) = 32),
    last_batch_sha256 bytea NOT NULL CHECK (octet_length(last_batch_sha256) = 32),
    imported_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_customer_id)
);
CREATE INDEX wcx_customers_phone_idx ON wcx_customers(phone_e164)
    WHERE phone_e164 IS NOT NULL;
-- Read-time inbox join (no FK, no approval state):
--   contacts resolved by canonical phone equality at query time; a
--   phone_shared row is shown as "shared" and its history is NOT merged.

CREATE TABLE wcx_cases (
    source text NOT NULL CHECK (source ~ '^[a-z0-9_-]{1,64}$'),
    source_case_id bigint NOT NULL CHECK (source_case_id > 0),
    source_customer_id bigint,
    source_code text,
    subject text,
    source_status integer,
    source_channel integer,
    source_agent_id bigint,
    created_local timestamp,
    updated_local timestamp,
    source_timezone text NOT NULL DEFAULT 'America/Bogota',
    created_at timestamptz,
    updated_at timestamptz,
    raw jsonb NOT NULL,
    source_fingerprint bytea NOT NULL CHECK (octet_length(source_fingerprint) = 32),
    first_batch_sha256 bytea NOT NULL CHECK (octet_length(first_batch_sha256) = 32),
    last_batch_sha256 bytea NOT NULL CHECK (octet_length(last_batch_sha256) = 32),
    imported_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_case_id),
    FOREIGN KEY (source, source_customer_id)
        REFERENCES wcx_customers(source, source_customer_id),
    CHECK (source_customer_id IS NULL OR source_customer_id > 0),
    CHECK (source_timezone = 'America/Bogota'),
    CHECK (
        (created_at IS NULL AND created_local IS NULL)
        OR (created_at IS NOT NULL AND created_local IS NOT NULL)
    )
);
CREATE INDEX wcx_cases_customer_timeline_idx
    ON wcx_cases(source, source_customer_id, created_local DESC, source_case_id DESC);

CREATE TABLE wcx_messages (
    source text NOT NULL,
    source_case_id bigint NOT NULL,
    source_message_id bigint NOT NULL CHECK (source_message_id > 0),
    source_type integer,
    actor text NOT NULL CHECK (actor IN ('customer', 'agent', 'automation')),
    is_admin boolean,
    is_owner boolean,
    is_automation boolean,
    body_text text,
    has_attachment boolean NOT NULL DEFAULT false,
    occurred_local timestamp,
    source_timezone text NOT NULL DEFAULT 'America/Bogota',
    occurred_at timestamptz,
    source_fingerprint bytea NOT NULL CHECK (octet_length(source_fingerprint) = 32),
    first_batch_sha256 bytea NOT NULL CHECK (octet_length(first_batch_sha256) = 32),
    last_batch_sha256 bytea NOT NULL CHECK (octet_length(last_batch_sha256) = 32),
    imported_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_case_id, source_message_id),
    FOREIGN KEY (source, source_case_id) REFERENCES wcx_cases(source, source_case_id),
    CHECK (source_timezone = 'America/Bogota'),
    CHECK (
        (occurred_at IS NULL AND occurred_local IS NULL)
        OR (occurred_at IS NOT NULL AND occurred_local IS NOT NULL)
    )
);
CREATE INDEX wcx_messages_case_timeline_idx
    ON wcx_messages(source, source_case_id, occurred_at, source_message_id);

-- Initial customer message rule (owner-verified): a movement with
-- idTicket = 0 belongs to its envelope when id = envelope id or it is the
-- first movement of the envelope. The previous "wrong case" category is
-- empty under this rule.

-- No commit. Guard removal alone still does not persist this draft.
ROLLBACK;
