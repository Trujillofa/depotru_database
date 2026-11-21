-- DRAFT ONLY. Not registered with any migration runner. NEVER APPLIED.
-- Target proposal: PostgreSQL in the inbox, NOT SmartBusiness/J3/Magento.
-- Deliberately abort before DDL even if somebody runs this entire file.
-- Future implementation needs owner approval and a separately reviewed migration.
BEGIN;
DO $$ BEGIN RAISE EXCEPTION 'DRAFT WCX import is not approved'; END $$;

CREATE TABLE wcx_customers (
    source text NOT NULL CHECK (source ~ '^[a-z0-9_-]{1,64}$'),
    source_customer_id bigint NOT NULL CHECK (source_customer_id > 0),
    phone_e164 text CHECK (phone_e164 ~ '^\+57(3[0-9]{9}|60[1245678][0-9]{7})$'),
    display_name text,
    contact_id text REFERENCES contacts(id) ON DELETE SET NULL,
    link_state text NOT NULL DEFAULT 'unreviewed'
        CHECK (link_state IN ('unreviewed', 'ambiguous', 'approved', 'rejected')),
    source_fingerprint bytea NOT NULL CHECK (octet_length(source_fingerprint) = 32),
    first_batch_sha256 bytea NOT NULL CHECK (octet_length(first_batch_sha256) = 32),
    last_batch_sha256 bytea NOT NULL CHECK (octet_length(last_batch_sha256) = 32),
    imported_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_customer_id),
    CHECK (contact_id IS NULL OR (link_state = 'approved' AND phone_e164 IS NOT NULL))
);
CREATE INDEX wcx_customers_phone_idx ON wcx_customers(phone_e164)
    WHERE phone_e164 IS NOT NULL;
CREATE UNIQUE INDEX wcx_customers_contact_idx ON wcx_customers(source, contact_id)
    WHERE contact_id IS NOT NULL;
CREATE UNIQUE INDEX wcx_customers_approved_phone_idx ON wcx_customers(source, phone_e164)
    WHERE contact_id IS NOT NULL AND phone_e164 IS NOT NULL;

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
    source_timezone text,
    created_at timestamptz,
    updated_at timestamptz,
    source_fingerprint bytea NOT NULL CHECK (octet_length(source_fingerprint) = 32),
    first_batch_sha256 bytea NOT NULL CHECK (octet_length(first_batch_sha256) = 32),
    last_batch_sha256 bytea NOT NULL CHECK (octet_length(last_batch_sha256) = 32),
    imported_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_case_id),
    FOREIGN KEY (source, source_customer_id)
        REFERENCES wcx_customers(source, source_customer_id),
    CHECK (source_customer_id IS NULL OR source_customer_id > 0),
    CHECK ((created_at IS NULL AND updated_at IS NULL) OR source_timezone IS NOT NULL)
);
CREATE INDEX wcx_cases_customer_timeline_idx
    ON wcx_cases(source, source_customer_id, created_local DESC, source_case_id DESC);

CREATE TABLE wcx_messages (
    source text NOT NULL,
    source_case_id bigint NOT NULL,
    source_message_id bigint NOT NULL CHECK (source_message_id > 0),
    source_type integer,
    actor text NOT NULL DEFAULT 'unknown'
        CHECK (actor IN ('customer', 'agent', 'automation', 'system', 'unknown')),
    body_text text,
    has_attachment boolean NOT NULL DEFAULT false,
    occurred_local timestamp,
    source_timezone text,
    occurred_at timestamptz,
    source_fingerprint bytea NOT NULL CHECK (octet_length(source_fingerprint) = 32),
    first_batch_sha256 bytea NOT NULL CHECK (octet_length(first_batch_sha256) = 32),
    last_batch_sha256 bytea NOT NULL CHECK (octet_length(last_batch_sha256) = 32),
    imported_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_case_id, source_message_id),
    FOREIGN KEY (source, source_case_id) REFERENCES wcx_cases(source, source_case_id),
    CHECK (occurred_at IS NULL OR source_timezone IS NOT NULL)
);
CREATE INDEX wcx_messages_case_timeline_idx
    ON wcx_messages(source, source_case_id, occurred_local, source_message_id);

-- No commit. Guard removal alone still does not persist this draft.
ROLLBACK;
