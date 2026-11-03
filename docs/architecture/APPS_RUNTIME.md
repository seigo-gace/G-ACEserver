# Independent app operation (F02 / S2)

> **2026-10-31 PC実機受入:** Master返却で2 project同時起動、片方の停止分離、stop/start後の永続化、設定更新/旧設定復帰、既存Core/Storage/他container不変、cleanupの全項目PASS（VERIFY=PASS/EXIT_CODE=0）。F02の汎用アプリ基盤としてこの範囲を受入済み。実Bot/Tumblrの機能、異image/DB migration rollback、Windows完全自動起動、VPN/Cloudflare/媒体/速度の受入は別Gate。正常な同一smokeを目的なく再実行しない。


Gserver hosts app-owned Docker Compose projects. The existing Core/API/Storage does not need redeployment to add an app. No Bot/Tumblr implementation, external Gateway/TGS connection, new runtime dependency or Web management UI is required.

## Local CLI

Use the existing WSL terminal, with the existing Docker/Compose installation and local app image. Keep app code/configuration in its own directory; private data and credentials stay outside Git. The CLI uses existing local Docker socket authority directly (root or an already-authorized group member), falling back to noninteractive sudo only when socket access is unavailable. `scripts/local_docker.py` pins the daemon to `unix:///var/run/docker.sock`; remote contexts and registry access are not selected. No group, socket permission or sudo policy is changed by the CLI. It does not build/pull images or delete app volumes.

```bash
# Only when the current shell lacks Docker socket access:
# sudo -v
python3 -B scripts/gserver_apps.py verify my-app /absolute/app/compose.yaml
python3 -B scripts/gserver_apps.py start my-app /absolute/app/compose.yaml
python3 -B scripts/gserver_apps.py status my-app /absolute/app/compose.yaml
python3 -B scripts/gserver_apps.py logs my-app /absolute/app/compose.yaml --show-logs
python3 -B scripts/gserver_apps.py stop my-app /absolute/app/compose.yaml
```

`start` waits up to 60 seconds for readiness (healthcheck when supplied). Repeating `start` applies changed configuration. For rollback, retain the previous app Compose/config and immutable local image, restore the previous definition, then `start` with the same app name. Persistent app volumes are retained. Image/config rollback does not undo a database migration: back up the app's data using its own compatible procedure before schema changes. A failed `start` retains containers/data for `status`/`logs` and recovery; it does not report successful deployment or automatically discard data.

Use unique lowercase names. Project `gace-app-<name>` isolates each app from `gace-gserver`. Default named networks/volumes stay within that project; explicit cross-project names, external resources, volume/network driver overrides, privilege/host namespaces, lifecycle hooks and Docker API socket exposure are refused. Bind mounts and secret/config files must resolve inside the app Compose directory; missing paths are refused. G:/F: originals are not mounted by the manager. Use app-owned named volumes for persistent container data. A separately authorized shared-data contract can be added later when an actual app needs it.

Only explicit loopback ports (`127.0.0.1`/`::1`) are permitted. App authors supply authentication when needed, resource limits, bounded logging, secrets, healthchecks and restart policies. The manager validates Compose then runs its private temporary canonical snapshot, so the operation does not reread a changed app definition or resolve credential values a second time. Snapshots are removed on normal/error exit. This is an Owner CLI for trusted app definitions, not a sandbox for hostile Compose authors or Docker administrators. Run operations for the same app sequentially.

`logs` defaults to metadata only; `--show-logs` explicitly displays the last 20 lines per service, capped at 64 KiB of displayed text. App logs may contain private data and must not be pasted into the public repository. Neither logs nor Compose configuration are written to Git by this CLI.

## One-command PC acceptance

```bash
bash scripts/smoke_gserver_apps_host.sh
```

This runs focused tests and authenticates sudo in that terminal only when direct Docker socket access is unavailable. It reuses the running Core's immutable local Python image for two synthetic app processes; no build/pull, production restart, external traffic, Host setting change or real app credentials are involved. Each app has its own guarded random project and fresh volume, nonroot/read-only process, no network/ports, dropped capabilities and bounded CPU/RAM/PIDs/logging.

The probe checks two simultaneous apps; stop isolation; stop/start persistence; configuration update and previous configuration restoration through container recreation; status/log access; authenticated Core `/ready` and `/files`; and unchanged IDs/images/start times/status/mounts for all pre-existing containers. Synthetic volumes and containers are removed on exit, including failure; production volumes are never selected. The test fails when Core/Storage is not already ready, Docker authority is absent, or a pre-existing container changes during the check. The image is reused without running the Gserver application/Worker inside the probes.

`APP_CONFIG_UPDATE_ROLLBACK` proves configuration recreation and data retention with one local image, not a two-image application migration. This is infrastructure acceptance; actual Bot/Tumblr functional tests stay in their app projects. `restart: unless-stopped` alone does not prove Windows boots WSL/Docker. Windows restart acceptance requires a separately authorized real reboot and subsequent service/data readback; no scheduled task is installed here.

## Fault tracing

| Symptom | Source / check | Recovery |
| --- | --- | --- |
| Docker CLI works but management asks for sudo | `scripts/local_docker.py`, `tests/test_local_docker.py` | Use the current authorized shell; after an owner-approved group change, reconnect or use `newgrp docker`. Kernel namespace/VPN helpers still require their existing sudo authority |
| Compose rejected | `scripts/gserver_apps.py`, `tests/test_gserver_apps.py` | Correct app-owned definition; `verify` before `start` |
| Start/readiness failure | App healthcheck, `status`, `logs --show-logs` | Fix app or restore previous Compose/image; `start` |
| Core/Storage failure | Existing `scripts/gserverctl.py`, Core release ledger | Existing Core recovery; do not replace with app configuration |
| PC probe failed | `scripts/smoke_gserver_apps_host.py`, result phase | Resolve exact phase; disposable resources cleaned; no Core reinstall |
| Windows reboot loses services | F01/F06, S2-04 | Inspect existing Windows/WSL/Docker startup before any Host changes |

## Independent app lifecycle acceptance (Composer PR #18 integration)

The original PC smoke demonstrated two independent app projects, stop isolation, persistent state and config rollback without changing Core/Storage. Reuse the existing `scripts/demo_independent_app_lifecycle.sh` only for an explicit repeatable owner-PC validation after any runtime integration. `restart` first restarts the app project without `compose down`, then waits for readiness via the existing immutable-image `up --no-build --pull never` operation. Stop/start and rollback retain named volumes. This integration preserves PR #15's safe logging and successful-probe diagnostic, rather than replacing them with the older PR #18 versions.

## VideoBot consumer contract acceptance

The active sales app is [`seigo-gace/create-videobot`](https://github.com/seigo-gace/create-videobot/pull/1), not GateApp-Bot or a legacy group Bot. Its app code, sales state and payment logic stay in that repository. Gserver owns execution and operational metadata admission; it does not accept purchase records, media IDs, customer IDs or payment values as logs. Tumblr remains a separate consumer, with its own GATE/MPB and OAuth contracts.

`scripts/smoke_videobot_integration.py` accepts an existing app source checkout or a verified temporary source snapshot and an immutable, already-local Node image. It checks the actual bootstrap/config/event adapter against the pinned upstream Git blobs at `ae8a2385d52d0579468c2e5cb2f3307f94524666`. It never clones, builds, pulls or changes the source. Source owners must keep that directory stable during execution. This is a trusted-owner acceptance tool, not a sandbox for arbitrary app authors.

```bash
python3 -B scripts/smoke_videobot_integration.py \
  --app-source /absolute/existing/create-videobot \
  --node-image node@sha256:025b8e975a61d94e33abeafaad1255ef44e4898cf1a1b6446860009c72e6d284
```

The exact Node linux/amd64 digest was resolved from the official Node22 Alpine manifest. The probe requires the healthy existing local Core/Storage as an invariant reference; it reuses its image in a disposable clone. Only the new clone, client containers, internal network and owned fresh volume are changed. No ports are published, the network is Docker `internal`, and the client is nonroot/read-only with bounded resources/logs. A synthetic Bot token enters client tmpfs by stdin. The synthetic Owner token stays in the clone. Token values never enter process arguments, environment, Source or evidence output.

On the owner PC, real upstream bootstrap/adapter admission, duplicate replay, conflicting content 409, wrong Bot credential 401, Bot rejection by the Owner-only API and clone restart/SQLite fingerprint preservation passed on 2026-11-04. All pre-existing containers and authenticated Core/Storage responses were unchanged; disposable resources were removed. The app's 37 offline Node tests also passed; Gserver's full 361 Python tests passed. `tests/test_videobot_integration.py` covers provenance rejection, secret diagnostics, cleanup on failure, refusal to remove foreign resources, internal-network admission and pre-existing-service invariants.

The upstream staging Compose currently requests build, a mutable local image tag and an external shared network. It is **not directly accepted** by `gserver_apps.py`: actual config-only inspection returned `EXTERNAL_RESOURCE_NOT_ALLOWED` as expected. Do not remove that guard or add the production Core to an app network to make this sample run. Production admission needs the app-owned immutable image, least-privilege credential supply, durable sales data and backup/restore, health/readiness and the adopted protected egress/ingress contract. The upstream bootstrap exits after one operational event; it is not a running Telegram sales service. No Telegram publishing, Stars charge/refund, payout, live Gateway/P015 or Tumblr OAuth acceptance is implied.
