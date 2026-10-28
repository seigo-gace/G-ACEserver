# Gserver Bot → existing Gateway → TGserver ZERO

## Priority and scope
Gserver must be usable for upcoming Telegram Bots immediately. Dev KB integration is deferred. Do not add a second TGserver, Gateway, Bot runtime, background AI task or public listener.

Existing transport: Bot module → Gserver POST /bot/events → durable local SQLite → Gateway POST /internal/events with destination tgserver-zero-bulk → TGserver ZERO /ingest/bulk → Telegram raw and Meilisearch.

## Local API
- POST /bot/events is authenticated with a separate Bot-only Bearer file, not the Owner management token. JSON fields: bot, event_id, event, optional level/outcome/error_code. Raw message text, chat/user IDs, usernames, file payloads, URLs and secrets are rejected. 202 means local durable queue only, not remote success; unchanged event replay is duplicate and changed payload is conflict 409.
- GET /bot/queue requires Owner authentication and returns only aggregate pending, sending, blocked, sent counts and whether Gateway is privately configured.
- Existing health, status, ready, files and download functionality stays separate.

Accepted operational types: bot.started, bot.stopped, bot.error, bot.recovered, bot.request.completed, bot.request.failed, bot.update.received, bot.delivery.completed, bot.delivery.failed. Generate a stable event_id once per Bot event, reuse it on retry.

## Existing Gateway contract
Producer sourceId=gserver-bot; stable eventId=gserver:<bot>:<event_id>; eventType=gserver.bot.operation; destinationId=tgserver-zero-bulk; body data.logs contains one sanitized log for project P015, assigned to existing TGserver group G002. Gateway 202 acknowledges the Gateway Event/Delivery/Outbox transaction; it does NOT prove downstream TGserver, Telegram raw or search delivery. Gateway receipt eventId belongs to Gateway and can differ from producer eventId.

SQLite uses WAL plus FULL synchronous, max 5000 outstanding, durable claims, bounded exponential retry, 20-attempt block and Owner-only bounded bot-retry after repairs. Sent receipt retention is at most seven days/20,000 events. No silent drop on unknown result.

## Existing Docker operations
- Existing Compose named state volume holds spool database and Bot-only auth token; Docker image is immutable; no new host port is opened except existing local-only 127.0.0.1:18765 after enable-local.
- gserverctl bot-init: create private Bot-only token in volume, never print value.
- gserverctl bot-smoke: local container HTTP event 202; local acceptance only.
- gserverctl bot-status: queue counts and private Gateway configuration state.
- gserverctl bot-gateway-config: operator explicitly enters private HTTPS Gateway URL and token; values travel through Docker stdin and are written to private volume files, not argv, source or GitHub.
- gserverctl bot-retry: explicitly requeue up to 100 blocked rows after fixing credentials/routing.
- scripts/gserver_bot_ready.py --install: owner-only test, bounded Docker preflight, immutable image build, existing gserverctl activation/rollback, loopback access, Bot-only token creation, real local smoke and status. Does not modify Windows/WSL drive mounts, G:/F: originals or Contabo.
- Future Bot containers must be explicitly attached to an authorized Docker network and receive only the Bot secret; never reuse the Owner API token.

## Source vs live status
TGserver source registry and ZERO central search reader map include Gserver P015/G002. Live TGserver registry deployment, five severity topic provisioning, Gateway destination configuration, credentials, real Telegram raw delivery, index/search correlation and Gserver Docker local Bot runtime are all NOT_VERIFIED until independently exercised.
Do not provision topics from Git history without auditing LIVE TGserver topics and state. Do not expose Gateway /internal/events to public Internet or bypass its existing access controls.

## Final acceptance
Real local Bot event must persist across restart, replay identically, deliver a Gateway durable 202, reach TGserver, appear in Telegram raw and indexed ZERO search with matching correlation; outage/restore must retain events. A Gserver healthy HTTP endpoint or local SQLite 202 is not this final E2E.