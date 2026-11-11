# Independent app operation (F02 / S2)

Gserver hosts app-owned Docker Compose projects. The existing Core/API/Storage does not need redeployment to add an app. No Bot/Tumblr implementation, external Gateway/TGS connection, new runtime dependency or Web management UI is required.

## Local CLI

Use the existing WSL terminal, with the existing Docker/Compose installation and local app image. Keep app code/configuration in its own directory; private data and credentials stay outside Git. The CLI uses local Docker via existing sudo authority, never a remote context or registry. It does not build/pull images or delete app volumes.

```bash
sudo -v
python3 -B scripts/gserver_apps.py verify my-app /absolute/app/compose.yaml
python3 -B scripts/gserver_apps.py start my-app /absolute/app/compose.yaml
python3 -B scripts/gserver_apps.py status my-app /absolute/app/compose.yaml
python3 -B scripts/gserver_apps.py logs my-app /absolute/app/compose.yaml --show-logs
python3 -B scripts/gserver_apps.py stop my-app /absolute/app/compose.yaml
python3 -B scripts/gserver_apps.py restart my-app /absolute/app/compose.yaml
```

`start` waits up to 60 seconds for readiness (healthcheck when supplied). `restart` recycles running containers without `compose down`, then waits again for readiness. Repeating `start` applies changed configuration. For rollback, retain the previous app Compose/config and immutable local image, restore the previous definition, then `start` with the same app name. Persistent app volumes are retained. Image/config rollback does not undo a database migration: back up the app's data using its own compatible procedure before schema changes. A failed `start` retains containers/data for `status`/`logs` and recovery; it does not report successful deployment or automatically discard data.

Use unique lowercase names. Project `gace-app-<name>` isolates each app from `gace-gserver`. Default named networks/volumes stay within that project; explicit cross-project names, external resources, volume/network driver overrides, privilege/host namespaces, lifecycle hooks and Docker API socket exposure are refused. Bind mounts and secret/config files must resolve inside the app Compose directory; missing paths are refused. G:/F: originals are not mounted by the manager. Use app-owned named volumes for persistent container data. A separately authorized shared-data contract can be added later when an actual app needs it.

Only explicit loopback ports (`127.0.0.1`/`::1`) are permitted. App authors supply authentication when needed, resource limits, bounded logging, secrets, healthchecks and restart policies. The manager validates Compose then runs its private temporary canonical snapshot, so the operation does not reread a changed app definition or resolve credential values a second time. Snapshots are removed on normal/error exit. This is an Owner CLI for trusted app definitions, not a sandbox for hostile Compose authors or Docker administrators. Run operations for the same app sequentially.

`logs` defaults to metadata only; `--show-logs` explicitly displays the last 20 lines per service, capped at 64 KiB of displayed text. App logs may contain private data and must not be pasted into the public repository. Neither logs nor Compose configuration are written to Git by this CLI.

## One-command PC acceptance

```bash
bash scripts/smoke_gserver_apps_host.sh
bash scripts/demo_independent_app_lifecycle.sh
```

The demo script runs the same 25 focused unit tests, then one disposable app through verify, start, restart, config update, Compose rollback, and stop on the running Core image.

This runs focused tests and authenticates sudo in that terminal. It reuses the running Core's immutable local Python image for two synthetic app processes; no build/pull, production restart, external traffic, Host setting change or real app credentials are involved. Each app has its own guarded random project and fresh volume, nonroot/read-only process, no network/ports, dropped capabilities and bounded CPU/RAM/PIDs/logging.

The probe checks two simultaneous apps; stop isolation; stop/start persistence; configuration update and previous configuration restoration through container recreation; status/log access; authenticated Core `/ready` and `/files`; and unchanged IDs/images/start times/status/mounts for all pre-existing containers. Synthetic volumes and containers are removed on exit, including failure; production volumes are never selected. The test fails when Core/Storage is not already ready, Docker authority is absent, or a pre-existing container changes during the check. The image is reused without running the Gserver application/Worker inside the probes.

`APP_CONFIG_UPDATE_ROLLBACK` proves configuration recreation and data retention with one local image, not a two-image application migration. This is infrastructure acceptance; actual Bot/Tumblr functional tests stay in their app projects. `restart: unless-stopped` alone does not prove Windows boots WSL/Docker. Windows restart acceptance requires a separately authorized real reboot and subsequent service/data readback; no scheduled task is installed here.

## Fault tracing

| Symptom | Source / check | Recovery |
| --- | --- | --- |
| Compose rejected | `scripts/gserver_apps.py`, `tests/test_gserver_apps.py` | Correct app-owned definition; `verify` before `start` |
| Start/readiness failure | App healthcheck, `status`, `logs --show-logs` | Fix app or restore previous Compose/image; `start` |
| Core/Storage failure | Existing `scripts/gserverctl.py`, Core release ledger | Existing Core recovery; do not replace with app configuration |
| PC probe failed | `scripts/smoke_gserver_apps_host.py`, result phase | Resolve exact phase; disposable resources cleaned; no Core reinstall |
| Windows reboot loses services | F01/F06, S2-04 | Inspect existing Windows/WSL/Docker startup before any Host changes |
