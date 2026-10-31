# ChatGPT → local Gserver development execution boundary (draft)

Status: DESIGN / NOT DEPLOYED / NOT AUTHORIZED BY SOURCE ALONE  
Owner: GPT CHAT for this separate change unit; Codex PR #15 and Composer app-side work are excluded.

## Purpose
Enable Master-directed GPT CHAT to inspect, test and eventually make admitted development changes on the **owner's Windows / WSL Ubuntu Gserver** without requiring Master to relay every shell command. Preserve the existing G-ACE GitHub Project / source-of-truth, and do not make normal Gserver operations depend on GitHub being online.

## Evidence at creation (2026-10-31)
- Canonical Gserver Current: [Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9); pending isolated-app/VPN work: [Draft PR #15](https://github.com/seigo-gace/G-ACEserver/pull/15).
- Existing server-core bounded-host registry `operations/github-project-bounded-host.json` registers Contabo checkouts; **G-ACEserver local Windows/WSL is not a registered execution host**.
- Existing Contabo CHAT path: server-core request → GitHub Actions → authenticated Gateway → Receiver → bounded Host Writer → correlated result. **Existing Contabo admission is not authority for the owner's PC.**
- GitHub code-search for a dedicated CHAT receiver in G-ACEserver yielded no match; absence from search is not proof of nonexistence. PC Runtime and live process state are UNKNOWN.
- Gserver Core and Docker/Compose integration exist separately from the remote CHAT execution proposal. No live operation is inferred.

## Boundaries and reuse requirements
1. Preserve current deployment, original G:/F: data, containers, existing app IDs and rollback ledgers. No Docker socket, root shell or secrets on public ingress.
2. Reuse existing G-ACE **control semantics** (Change Unit, owner, repository/branch/HEAD, immutable request ID, scope and outcome), not Contabo's Host identity or unrestricted execution permissions.
3. The **PC-local execution authority** must be separately authenticated, host-bound, deny-by-default, time-bounded, scoped to already registered local repository/owned nested worktree and bounded commands; read-only probe before write acceptance.
4. Reuse approved infrastructure where possible. No duplicate central Gateway, project control plane, new permanent token or tunnel solely to satisfy this document. The exact transport to the PC remains UNSELECTED pending verification of existing G-ACE-domain ingress and PC connectivity.
5. Astera-zone routes are reserved for Astera; do not use them for non-Astera Gserver traffic without Master's explicit exact-purpose/hostname approval. Existing Cloudflare resources must not be altered by this change unit.
6. Never transport credential values, private logs, raw stdout or host-specific inventory into the **public** G-ACEserver repository, public GitHub Issues or public Actions artifacts.
7. For each request: verify authenticated origin and replay/idempotency → exact Project/CU/effect/target → local repository ownership and HEAD → execution isolation/timeout → bounded durable result → correlate the original request ID. A timeout or missing result is UNKNOWN, not automatic command retry.
8. Server-side platform rules and service-provider mutations are owned elsewhere. No changes to server-core Rule Plane, shared Gateway or Contabo runtime under this Gserver CU.

## Private handoff readback: existing Cloudflare prerequisite (2026-10-31)
The authoritative Gserver/TGserver handoff in Notion (2026-10-29) records Master's clarification: the G-ACE Cloudflare domain(s) had been used for mail, **not registered or connected to Gserver**. `g-acebot.com` was the previously chosen G-ACE primary domain; `g-acebot.jp` is a **different zone** raised for preparation. Neither is assumed live or interchangeable. The existing Vault Cloudflare API context returned zone NOT_LISTED for both (not proof of nonownership); initial account token generation, Vault enrollment and official Cloudflare MCP OAuth approval remained unverified. Protect existing email MX/SPF/DKIM/DMARC; do not invent a hostname or repurpose the Astera zone. A single historical Bot→Gateway→TGserver E2E was confirmed under an **unauthorized-for-future-use Astera route** and is not authority for new messages.

Therefore **remote CHAT-to-PC commands cannot be accepted as live or ready** merely from the existing Contabo route, GitHub PR or past Bot probe. Confirm correct Cloudflare account and target zone through owner-authorized means, and verify whether a permitted private PC ingress already exists before any receiver deployment. No credentials or DNS are requested by this documentation-only change.

## Implementation decomposition
- **A (read-only feasibility):** Observe actual Gserver WSL/PC service state, existing approved Cloudflare G-ACE ingress, accessible broker/receiver and relevant private policy without copying secrets. Establish whether an existing permitted local ingress and authorized Host executor already exist.
- **B (minimum admitted transport):** Only if A proves a missing local boundary, add the smallest Gserver-owned adapter to the existing approved transport, with independently checked authentication and local admission. Write negative tests first: unauthorized/replayed request, wrong host/repo/CU, stale SHA, unregistered path, symlink escape, dirty worktree, unexpected effect, unavailable target, sensitive output.
- **C (correlated read-only E2E):** CHAT submits a unique authorized read-only request, PC executes once, private correlated result returns, and CHAT independently verifies request ID, source SHA, exit code and output handling.
- **D (bounded development E2E):** After C, separately admit an owned reversible source/test operation; verify change ownership, artifact, rollback and absence of effects on PR #15, Composer work and live Core.
- **E (runtime independence):** During GitHub unavailability, existing local Gserver apps and storage continue operating. This is not a requirement that CHAT remote development requests work without GitHub.

## Acceptance / truth labels
- SOURCE_CONTRACT: this document exists in a branch, not runtime.
- LOCAL_CONNECTIVITY: UNKNOWN until observed on owner's PC.
- AUTHENTICATED_PC_HOST_EXECUTOR: NOT_VERIFIED.
- READ_ONLY_CHAT_TO_PC_RESULT: NOT_VERIFIED.
- SAFE_REVERSIBLE_CHAT_TO_PC_CHANGE: NOT_VERIFIED.
- CORE/PR15/COMPOSER_NON_REGRESSION: NOT_VERIFIED.
- PROD_READY: NO.

## Exact next action
Read-only inventory in the existing owner WSL: registered processes, existing listener/broker, G-ACE-zone Tunnel/Access ownership and repo HEAD/dirty status; redact secrets. Select the smallest existing authorized route from those facts, then implement the missing local adapter and test it. Do not provision public ingress, a new token, or touch Codex PR #15 as a substitute for this gate.
