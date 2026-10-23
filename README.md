# G-ACEserver

> **Status: DESIGN_MIGRATION / RUNTIME_NOT_VERIFIED**

Gserver is a self-hosted service platform on the owner's Windows PC and Ubuntu/WSL environment. The goal is one resource-efficient environment for web applications, bots, large-file storage, the existing G-ACE Development Knowledge Base, and integration with existing TGserver (TGS) for logs and encrypted off-site backups.

## Start here

1. Read [`AGENTS.md`](AGENTS.md) for bounded Codex/AI execution and existing G-ACE rules.
2. Read [`docs/CURRENT.md`](docs/CURRENT.md) for the current mission, evidence states, and the next task.
3. Read [`docs/requirements/FINAL_ACCEPTANCE.md`](docs/requirements/FINAL_ACCEPTANCE.md) and [`docs/architecture/OVERVIEW.md`](docs/architecture/OVERVIEW.md).
4. Read the relevant [`docs/tasks`](docs/tasks) stage, inspect **existing source/runtime**, and implement one accepted change unit without replacing working components.
5. Keep relevant Issue state and the current documentation synchronized with the actual code/validation evidence.

## Scope and safety

- This is the **local PC Gserver**, not the separate Contabo VPS. Do not deploy, move, or modify unrelated VPS services.
- Reuse existing nginx/aaPanel, G-ACE KB (`seigo-gace/gace-dev-kb`) and TGserver capabilities before creating a second implementation.
- Protect original KB/data and rollback evidence. Never treat a health endpoint as proof of a complete web/bot/KB/backup service.
- Separate FACT, historical report, proposal, and UNKNOWN. Source/CI PASS is not runtime or restoration PASS.
- The repository is currently **public**. Never commit secrets, private tokens, passwords, real user data, security incident artifacts, precise internal network details, or private inventories.
- Do not add workflows, tokens, long-lived agents or paid AI execution without the required existing authority.

## Provenance

This repository is being initialized from an existing Notion design/task corpus (F01–F08, S0–S7, 46 tasks). Migrated documentation is a *design baseline*, not proof of deployment. Host inventory, source reconciliation, and exact tests remain tasks.
