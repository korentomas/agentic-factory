CREATE TABLE "accounts" (
	"user_id" text NOT NULL,
	"type" text NOT NULL,
	"provider" text NOT NULL,
	"provider_account_id" text NOT NULL,
	"refresh_token" text,
	"access_token" text,
	"expires_at" integer,
	"token_type" text,
	"scope" text,
	"id_token" text,
	"session_state" text,
	CONSTRAINT "accounts_provider_provider_account_id_pk" PRIMARY KEY("provider","provider_account_id")
);
--> statement-breakpoint
CREATE TABLE "agent_outcomes" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"outcome" text NOT NULL,
	"pr_url" text NOT NULL,
	"pr_number" integer NOT NULL,
	"branch" text NOT NULL,
	"risk_tier" text NOT NULL,
	"checks_gate" text,
	"checks_tests" text,
	"checks_review" text,
	"checks_spec_audit" text,
	"files_changed" json DEFAULT '[]'::json,
	"review_findings" json DEFAULT '[]'::json,
	"run_id" text,
	"model" text,
	"review_model" text,
	"provider" text,
	"engine" text,
	"cost_usd" numeric(10, 4),
	"duration_ms" integer,
	"num_turns" integer,
	"timestamp" timestamp DEFAULT now() NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "repositories" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"github_repo_id" integer NOT NULL,
	"full_name" text NOT NULL,
	"installation_id" integer NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "sessions" (
	"session_token" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"expires" timestamp NOT NULL
);
--> statement-breakpoint
CREATE TABLE "subscriptions" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"stripe_customer_id" text NOT NULL,
	"stripe_subscription_id" text,
	"stripe_price_id" text,
	"plan_id" text NOT NULL,
	"status" text DEFAULT 'active' NOT NULL,
	"current_period_start" timestamp,
	"current_period_end" timestamp,
	"cancel_at_period_end" boolean DEFAULT false NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "subscriptions_stripe_subscription_id_unique" UNIQUE("stripe_subscription_id")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text,
	"email" text,
	"email_verified" timestamp,
	"image" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "verification_tokens" (
	"identifier" text NOT NULL,
	"token" text NOT NULL,
	"expires" timestamp NOT NULL,
	CONSTRAINT "verification_tokens_identifier_token_pk" PRIMARY KEY("identifier","token")
);
--> statement-breakpoint
ALTER TABLE "accounts" ADD CONSTRAINT "accounts_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agent_outcomes" ADD CONSTRAINT "agent_outcomes_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "repositories" ADD CONSTRAINT "repositories_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "accounts_user_id_idx" ON "accounts" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "agent_outcomes_user_id_idx" ON "agent_outcomes" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "agent_outcomes_outcome_idx" ON "agent_outcomes" USING btree ("outcome");--> statement-breakpoint
CREATE INDEX "agent_outcomes_timestamp_idx" ON "agent_outcomes" USING btree ("timestamp");--> statement-breakpoint
CREATE INDEX "agent_outcomes_run_id_idx" ON "agent_outcomes" USING btree ("run_id");--> statement-breakpoint
CREATE INDEX "agent_outcomes_engine_idx" ON "agent_outcomes" USING btree ("engine");--> statement-breakpoint
CREATE INDEX "agent_outcomes_model_idx" ON "agent_outcomes" USING btree ("model");--> statement-breakpoint
CREATE INDEX "agent_outcomes_risk_tier_idx" ON "agent_outcomes" USING btree ("risk_tier");--> statement-breakpoint
CREATE INDEX "repositories_user_id_idx" ON "repositories" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "repositories_github_repo_id_idx" ON "repositories" USING btree ("github_repo_id");--> statement-breakpoint
CREATE INDEX "repositories_installation_id_idx" ON "repositories" USING btree ("installation_id");--> statement-breakpoint
CREATE INDEX "sessions_user_id_idx" ON "sessions" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "subscriptions_user_id_idx" ON "subscriptions" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "subscriptions_stripe_customer_id_idx" ON "subscriptions" USING btree ("stripe_customer_id");--> statement-breakpoint
CREATE INDEX "subscriptions_stripe_subscription_id_idx" ON "subscriptions" USING btree ("stripe_subscription_id");