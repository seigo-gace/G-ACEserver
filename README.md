# G-ACEserver

> **Status: DESIGN_MIGRATION / RUNTIME_NOT_VERIFIED**

Gserver is a self-hosted service platform on the owner's Windows PC and Ubuntu/WSL environment. The goal is one resource-efficient environment for web applications, bots, large-file storage, the existing G-ACE Development Knowledge Base, and integration with existing TGserver (TGS) for logs and encrypted off-site backups.

## Start here

1. Read [`AGENTS.md`](AGENTS.md) for bounded Codex/AI execution and existing G-ACE rules.
2. Read [`docs/CURRENT.md`](docs/CURRENT.md) for the current mission, evidence states, and the next task.
3. Read [`docs/requirements/FINAL_ACCEPTANCE.md`](docs/requirements/FINAL_ACCEPTANCE.md) and [`docs/architecture/OVERVIEW.md`](docs/architecture/OVERVIEW.md).
4. Read the relevant [`docs/tasks`](docs/tasks) stage, inspect **existing source/runtime**, and implement one accepted change unit without replacing working components.
5. Keep relevant Issue state and the current documentation synchronized with the actual code/validation evidence.

## 採用：GitHub開発管理とGserver通常運用の分離

- GitHubは開発管理・履歴・ソース配布専用。PC Gserverの通常起動、Web/API、Bot、G:ストレージ、既存KB検索/単一Current、ローカル復旧にはGitHub接続・認証・Actionsを要求しない。
- Git由来のKB出典/Commit SHAは維持する。新しい資料の受領と、受領済みローカルCurrentの通常利用を区別する。
- TGSは別Hostのログ・暗号化バックアップ先。TGSへの通信が止まってもローカル機能をGitHubへ迂回させず、上限付き保留・失敗表示にする（実PCでは未検証）。
- 完成・公開履歴/秘密混入監査の後に、このGitHub RepoをPrivateへ変更する。今はPublicであり実機情報・秘密は置かない。

## Scope and safety

- This is the **local PC Gserver**, not the separate Contabo VPS. Do not deploy, move, or modify unrelated VPS services.
- Reuse existing nginx/aaPanel, G-ACE KB (`seigo-gace/gace-dev-kb`) and TGserver capabilities before creating a second implementation.
- Protect original KB/data and rollback evidence. Never treat a health endpoint as proof of a complete web/bot/KB/backup service.
- Separate FACT, historical report, proposal, and UNKNOWN. Source/CI PASS is not runtime or restoration PASS.
- The repository is currently **public**. Never commit secrets, private tokens, passwords, real user data, security incident artifacts, precise internal network details, or private inventories.
- Do not add workflows, tokens, long-lived agents or paid AI execution without the required existing authority.

## Provenance

This repository is being initialized from an existing Notion design/task corpus (F01–F08, S0–S7, 46 tasks). Migrated documentation is a *design baseline*, not proof of deployment. Host inventory, source reconciliation, and exact tests remain tasks.

## GitHub Current / task execution

- **[CURRENT Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9)** is the entry point for every new ChatGPT development chat and PC Codex session.
- Stage Issues: [S0 #1](https://github.com/seigo-gace/G-ACEserver/issues/1) · [S1 #2](https://github.com/seigo-gace/G-ACEserver/issues/2) · [S2 #3](https://github.com/seigo-gace/G-ACEserver/issues/3) · [S3 #4](https://github.com/seigo-gace/G-ACEserver/issues/4) · [S4 #5](https://github.com/seigo-gace/G-ACEserver/issues/5) · [S5 #6](https://github.com/seigo-gace/G-ACEserver/issues/6) · [S6 #7](https://github.com/seigo-gace/G-ACEserver/issues/7) · [S7 #8](https://github.com/seigo-gace/G-ACEserver/issues/8).
- 46 task definitions live in `docs/tasks/S0.md`–`S7.md`; the Issues have completion checklists.
- This public repository contains documentation only at bootstrap; the PC application source has **not** been imported or deployment-proven.
