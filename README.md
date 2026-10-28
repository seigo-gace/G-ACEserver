# G-ACEserver

> **Status: BOT/TGS SOURCE_IMPLEMENTED / GSERVER_BOT_DOCKER_E2E_PENDING**

The existing Python prototype is now imported and packaged with an immutable-base Dockerfile, persistent bounded logs, an authenticated status UI/API, and offline Compose lifecycle/rollback tooling. See [current evidence](docs/CURRENT.md) and [runtime operation boundary](docs/architecture/RUNTIME_S2.md). The base deployment exposes no host ports and mounts no original data. Container execution is pending local sudo authentication; this is not final production acceptance.

Gserver is a Docker/Compose-first self-hosted service platform on the owner's Windows PC / WSL Ubuntu, designed to share an operational contract with existing Contabo Docker hosts and future additional servers. Its goal is one resource-efficient, extensible pseudo-cloud of web applications, independent services, storage, the existing G-ACE Development Knowledge Base, and TGserver (TGS) logging/backup integrations. The source design is adopted; Gserver Docker runtime is NOT deployed or verified.

## Immediate priority — Telegram Bot-ready Gserver

Implement the Bot local runtime and existing TGserver ZERO connection first; Dev KB is postponed by the owner. See [Bot-to-TGserver contract](docs/architecture/BOT_TGS_BRIDGE.md), [safe one-shot Bot-ready installation](scripts/gserver_bot_ready.py), and [Current](docs/CURRENT.md). Telegram live delivery is NOT VERIFIED despite TGserver source registry CI PASS.

## Start here

1. Read [`AGENTS.md`](AGENTS.md) for bounded Codex/AI execution and existing G-ACE rules.
2. Read [`docs/CURRENT.md`](docs/CURRENT.md) for the current mission, evidence states, and the next task.
3. Read [`docs/requirements/FINAL_ACCEPTANCE.md`](docs/requirements/FINAL_ACCEPTANCE.md) and [`docs/architecture/OVERVIEW.md`](docs/architecture/OVERVIEW.md).
4. Read the relevant [`docs/tasks`](docs/tasks) stage, inspect **existing source/runtime**, and implement one accepted change unit without replacing working components.
5. Keep relevant Issue state and the current documentation synchronized with the actual code/validation evidence.

## 採用：Dockerコンテナ主体・複数サーバー共通運用

- **通常のWeb/API/KB/TGS接続等をDockerコンテナ単位に分割**し、各ホストはDocker Engine + Docker Composeを基本とする。ホスト依存（Windows/WSL起動、USB mount、Firewall、daemon）だけはHost管理。Contabo既存Docker環境を変更しない。
- **GserverとContabo等の共通項は運用契約**（サービス定義、名前、health、ログ、resource bound、secretの渡し方、永続volume、backup/restore、更新/rollback）。Windowsのドライブパス等、物理Host固有の設定値まで同一化しない。
- VS Code + WSL UbuntuをGserver操作入口とし、Windowsに開発用Node/Python/Dockerを二重導入する前提にしない。増設時もコンテナ/Compose単位で追加・分離し、必要以上の共通集中基盤を最初から作らない。
- **現在のWSL実測:** Docker Engine導入済み（引継ぎ29.9.2）、Compose v5.6.1を現セッションで確認。既存Podman等は維持。本体の修正後Docker起動はsudo認証待ちで未検証。10/23の`docker=NOT_FOUND`は過去記録。
- Copilot製ローカルPython HTTP試作の稼働は、Docker化済み/本番設計完了を示さない。正式設計と移行単位は[OVERVIEW](docs/architecture/OVERVIEW.md)と[S2](docs/tasks/S2.md)に統一。Telegram系5資産の採否は別作業。

## 採用：GitHub開発管理とGserver通常運用の分離

- GitHubは開発管理・履歴・ソース配布専用。PC Gserverの通常起動、Web/API、Bot、G:ストレージ、既存KB検索/単一Current、ローカル復旧にはGitHub接続・認証・Actionsを要求しない。
- Git由来のKB出典/Commit SHAは維持する。新しい資料の受領と、受領済みローカルCurrentの通常利用を区別する。
- TGSは別Hostのログ・暗号化バックアップ先。TGSへの通信が止まってもローカル機能をGitHubへ迂回させず、上限付き保留・失敗表示にする（実PCでは未検証）。
- 完成・公開履歴/秘密混入監査の後に、このGitHub RepoをPrivateへ変更する。今はPublicであり実機情報・秘密は置かない。

## Scope and safety

- This is the **local PC Gserver**, not the separate Contabo VPS. Do not deploy, move, or modify unrelated VPS services.
- Identify existing nginx/aaPanel dependencies before retention or safe retirement; reuse the actual needed functions rather than retaining aaPanel as a mandatory final component. Reuse G-ACE KB (`seigo-gace/gace-dev-kb`) and TGserver capabilities before creating a second implementation.
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
- This public repository contains the adapted existing PC application, packaging, lifecycle tools and tests. Original PC configuration/data/logs are excluded. Production deployment and final acceptance remain unverified.
