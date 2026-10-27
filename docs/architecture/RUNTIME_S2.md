# S2 runtime packaging and operations

Owner: Codex. Existing F01–F08 / 46 tasks remain unchanged.

## Source and boundary

`app/gserver.py` derives from the existing 109-line Python standard-library prototype (SHA256 `41e0df51db854fd562f748b4f8dbcc558d0052d2d52d2957f6d3a89b9f61e15c`). The original file, configuration, data and logs were not modified. No framework or duplicate KB/TGS implementation was introduced.

Dockerfile pins the official Python linux/amd64 manifest digest. Python standard library only; no pip dependencies. The Docker build allowlist includes only three application files. Host config, credentials, private logs and data cannot enter the image through this build context.

The packaged Compose base is deliberately isolated pending ingress/credential/mount approval: no network, no published ports, no G:/F: bind mounts, no Docker socket. Nonroot, read-only rootfs, bounded tmpfs, CPU/RAM/PID limits, healthcheck, restart policy. It is an executable packaging baseline, not a completed production integration. `/health` checks process liveness only; `/ready` requires authorization and a storage mount and explicitly reports KB/TGS as not integrated. The UI reports incomplete features.

## Persistence and operation

`/var/lib/gserver` is a named Docker volume on the Docker host filesystem. Image-created ownership is UID/GID 65534. File logs rotate at 1 MiB with four backups. Docker output uses the bounded local logging driver. The existing source staging tmpfs remains ephemeral and is not used as production log persistence.

`scripts/gserverctl.py` operates only project `gace-gserver` using local immutable image IDs (`sha256:…`). It never pulls, fetches, prunes, removes volumes, or modifies other services. `activate IMAGE_ID` waits for health and records current/previous versions; a failed update attempts the previously recorded image. `start`, `stop`, `status`, `logs`, `rollback` use the stored local release record. Concurrent operations are rejected by a local lock. An existing project without a release record is not automatically adopted. Release records live outside Git in the user's state directory.

Operations use existing sudo authority; credentials are never read by this script. Invoke it as the normal user after terminal sudo authentication, keeping the release ledger under that user. Do not run the Python controller through sudo. First-install failure stops the test service but retains its volume for inspection. An atomic pending journal precedes activation. State-write failure or process interruption blocks subsequent operations until `recover` restores the committed release (or stops an uncommitted first installation). Failed recovery retains the journal. No automatic deletion/adoption is implemented.

Storage endpoints are still read-only capacity checks. Missing mounts or stat failures return 503 rather than reporting the host root disk as G:. This is not yet a USB identity/ACL implementation. Protected routes use an externally provisioned bearer credential file of at least 32 bytes; no fallback password/token is generated. Credential provisioning and ingress publication remain separate protected actions. No browser persistent storage is used for the credential. Production ingress must terminate TLS and enforce request limits before any non-loopback access is considered.

## Verification and rollback

`python3 -m unittest discover -s tests -v` covers live temporary loopback HTTP, authentication failures, missing/disappearing storage, secret-safe request logging, UI assets, and lifecycle failure/rollback with a mocked Docker boundary. Those tests are not Docker runtime evidence.

`bash scripts/smoke_gserver_staging.sh` verifies the original source in the existing isolated staging container. `bash scripts/smoke_gserver_runtime.sh` builds the packaged image, starts an isolated dedicated project, verifies persistent logs across container recreation, stops/starts it with no external network, checks existing services, and removes only the newly created test project's containers/volume. It refuses to reuse pre-existing test containers or volumes. Build images/cache are retained; there is no prune. This test does not deploy production or prove real backup restore.

For production rollback, the controller activates the previous local image against the same volume. No data migration is currently performed. Once mutable application schemas are added, a compatible snapshot/restore gate must precede update; image rollback alone is not data rollback.

## Remaining acceptance

- S2-01/02: actual image build and volume ownership/readback, approved Linux source/config placement, existing runtime dependency exceptions.
- S2-03: ingress and pre-existing proxy integration, owner-provided credential and permitted bind, browser E2E.
- S2-04: existing Windows startup inventory, host/WSL startup configuration approval, actual reboot proof. `restart: unless-stopped` alone does not start WSL after Windows reboot or restart an unhealthy live process.
- S2-05: real previous-version rollback and interruption recovery; current mocked failure tests do not close this gate.
- S3–S7: authorized storage file operations and drive identity, existing KB migration, actual TGS contracts, backup/restore, Bot choice, monitoring and final PC E2E.

No Contabo changes, Windows settings, existing services, original drives or secrets were modified.
