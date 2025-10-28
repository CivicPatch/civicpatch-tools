-- Create "atlas_schema_revisions" table
CREATE TABLE "atlas_schema_revisions" (
  "version" character varying NOT NULL,
  "description" character varying NOT NULL,
  "type" bigint NOT NULL DEFAULT 2,
  "applied" bigint NOT NULL DEFAULT 0,
  "total" bigint NOT NULL DEFAULT 0,
  "executed_at" timestamptz NOT NULL,
  "execution_time" bigint NOT NULL,
  "error" text NULL,
  "error_stmt" text NULL,
  "hash" character varying NOT NULL,
  "partial_hashes" jsonb NULL,
  "operator_version" character varying NOT NULL,
  PRIMARY KEY ("version")
);
-- Create "users" table
CREATE TABLE "users" (
  "id" serial NOT NULL,
  "email" text NOT NULL,
  "provider" text NOT NULL,
  "provider_user_id" text NOT NULL,
  "server_url" text NULL,
  "is_approved" boolean NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CONSTRAINT "users_provider_provider_user_id_key" UNIQUE ("provider", "provider_user_id")
);
-- Create index "users_provider_provider_user_id" to table: "users"
CREATE UNIQUE INDEX "users_provider_provider_user_id" ON "users" ("provider", "provider_user_id");
-- Create "api_keys" table
CREATE TABLE "api_keys" (
  "id" serial NOT NULL,
  "provider" text NOT NULL DEFAULT 'github',
  "provider_user_id" text NOT NULL,
  "api_key_suffix" text NOT NULL,
  "api_key_hash" text NOT NULL,
  "created_at" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  "revoked_at" timestamp NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "fk_api_keys_user" FOREIGN KEY ("provider", "provider_user_id") REFERENCES "users" ("provider", "provider_user_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "logs" table
CREATE TABLE "logs" (
  "id" serial NOT NULL,
  "api_key_id" integer NULL,
  "action" text NOT NULL,
  "type" text NOT NULL,
  "timestamp" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id"),
  CONSTRAINT "fk_logs_api_key" FOREIGN KEY ("api_key_id") REFERENCES "api_keys" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
