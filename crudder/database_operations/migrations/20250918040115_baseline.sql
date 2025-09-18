-- Create "users" table
CREATE TABLE `users` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `email` text NOT NULL,
  `provider` text NOT NULL,
  `provider_user_id` text NOT NULL,
  `server_url` text NULL
);
-- Create index "users_provider_provider_user_id" to table: "users"
CREATE UNIQUE INDEX `users_provider_provider_user_id` ON `users` (`provider`, `provider_user_id`);
-- Create "api_keys" table
CREATE TABLE `api_keys` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `provider` text NOT NULL DEFAULT 'github',
  `provider_user_id` text NOT NULL,
  `api_key_suffix` text NOT NULL,
  `api_key_hash` text NOT NULL,
  `created_at` timestamp NULL DEFAULT (CURRENT_TIMESTAMP),
  `revoked_at` timestamp NULL,
  CONSTRAINT `0` FOREIGN KEY (`provider`, `provider_user_id`) REFERENCES `users` (`provider`, `provider_user_id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "logs" table
CREATE TABLE `logs` (
  `id` integer NULL PRIMARY KEY AUTOINCREMENT,
  `api_key_id` integer NULL,
  `action` text NOT NULL,
  `type` text NOT NULL,
  `timestamp` timestamp NULL DEFAULT (CURRENT_TIMESTAMP),
  CONSTRAINT `0` FOREIGN KEY (`api_key_id`) REFERENCES `api_keys` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
