CREATE TABLE `operations` (
	`id` text PRIMARY KEY NOT NULL,
	`request_hash` text NOT NULL,
	`response` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `runs` (
	`id` text PRIMARY KEY NOT NULL,
	`workspace_id` text NOT NULL,
	`operation_id` text NOT NULL,
	`request_hash` text NOT NULL,
	`question` text NOT NULL,
	`scope` text NOT NULL,
	`expected_version` integer NOT NULL,
	`status` text NOT NULL,
	`events` text NOT NULL,
	`context` text NOT NULL,
	`result` text,
	`created` integer NOT NULL,
	`day` text NOT NULL,
	`charged_tokens` integer NOT NULL,
	`usage_uncertain` integer NOT NULL,
	`lease_token` text,
	`lease_expires` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `run_operation` ON `runs` (`workspace_id`,`operation_id`);--> statement-breakpoint
CREATE INDEX `run_budget` ON `runs` (`day`,`workspace_id`);--> statement-breakpoint
CREATE INDEX `active_runs` ON `runs` (`workspace_id`,`status`);--> statement-breakpoint
CREATE TABLE `sessions` (
	`digest` text PRIMARY KEY NOT NULL,
	`workspace_id` text NOT NULL,
	`expires` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `workspaces` (
	`id` text PRIMARY KEY NOT NULL,
	`version` integer NOT NULL,
	`state` text NOT NULL,
	`last_operation` text
);
