# G-ACEserver

> **Status: local Core / authentication / G: Storage verified by owner; generic app infrastructure accepted by owner; VPN/Cloudflare runtime acceptance remains open.**

Gserver is a general-purpose Docker/Compose server on the owner's Windows PC / WSL Ubuntu. Independent apps own their code, images, Compose definitions and data. Telegram Bot and Tumblr are app examples; TGserver provides separate logging/backup services. Local Core/Storage operation needs no GitHub or external service. Protected app egress and cloudflared connections require VPN routing, preserved Cloudflare defenses, and verified privacy/performance/recovery gates; see [reviewed privacy design](docs/handoffs/TELEGRAM_VPN_PRIVACY_2026-10-30.md) and [implementation](docs/architecture/VPN_RUNTIME.md).

The existing Core and Storage remain running. [PR #15](https://github.com/seigo-gace/G-ACEserver/pull/15) adds the independent app CLI; see [app operation and acceptance](docs/architecture/APPS_RUNTIME.md) and [current evidence](docs/CURRENT.md). Management uses the existing VS Code/Cursor WSL terminal. The full [F01–F08 acceptance](docs/requirements/FINAL_ACCEPTANCE.md) remains open.

## Workspace / server-core

The existing server-core is also the local workspace command center. [Workspace integration](docs/architecture/WORKSPACE_SERVERCORE.md) tracks the existing ServerTerminal and GitHub Project Agent Loop continuation. `python3 -B scripts/gserver_workspace.py` verifies the local workspace wiring; explicit `--install` creates missing files and refuses conflicting existing files. Layout verification does not establish client rule loading or remote Host admission.

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
- **現在のWSL実測:** Docker Engine導入済み（引継ぎ29.9.2）、Compose v5.6.1を現セッションで確認。既存Podman等は維持。10/30のOwner実機検証で既存Core Healthy・認証付きStorage API 200。独立アプリE2Eと再起動復帰は別途未受入。10/23の`docker=NOT_FOUND`は過去記録。
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
