BEGIN;

-- Create "users" table
CREATE TABLE IF NOT EXISTS "users" (
  "email" text NOT NULL,
  "provider" text NOT NULL,
  "provider_user_id" text NOT NULL,
  "server_url" text NULL,
  "is_approved" boolean NULL DEFAULT false,
  "created_at" timestamptz DEFAULT now(),
  PRIMARY KEY ("provider", "provider_user_id")
);

-- Create "api_keys" table
CREATE TABLE IF NOT EXISTS "api_keys" (
  "id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  "provider" text NOT NULL DEFAULT 'github',
  "provider_user_id" text NOT NULL,
  "api_key_suffix" text NOT NULL,
  "api_key_hash" text NOT NULL,
  "created_at" timestamptz DEFAULT now(),
  "revoked_at" timestamptz NULL,
  FOREIGN KEY ("provider", "provider_user_id") REFERENCES "users" ("provider", "provider_user_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);

-- Create "logs" table
CREATE TABLE IF NOT EXISTS "logs" (
  "id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  "api_key_id" integer NULL,
  "action" text NOT NULL,
  "type" text NOT NULL,
  "created_at" timestamptz DEFAULT now(),
  FOREIGN KEY ("api_key_id") REFERENCES "api_keys" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);

COMMIT;
