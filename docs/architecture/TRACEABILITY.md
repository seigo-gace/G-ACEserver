# 完成条件・実装・障害トレーサビリティ
| Requirement | Component | Related tasks | 受入証拠 |
| --- | --- | --- | --- |
| F01 | Windows Boot/WSL/Runtime | S1-02/07; S2-02/04 | 実起動・二重常駐解消 |
| F02 | Web/API/独立Compose Apps/Bot（管理UI非必須） | S1-03/04; S2-03; S3-01/05; S5-01 | 独立サービス・UXとE2E |
| F03 | G: storage adapter | S1-01/04; S3-02..05 | 認証/転送/SHA/脱着安全 |
| F04 | G-ACE KB MVS/Current | S1-05; S4-01..06 | ACTIVE+rollback/MCP/Deep parity |
| F05 | TGS producer, backup client | S1-06; S5-02..06 | 同一イベントraw/index+隔離復元 |
| F06 | OS/OSS防御・監視 | S1-07; S6-01..06 | 公開面/通知/復旧/資源 |
| F07 | Registry/evidence map | S0全体; S7-05 | 症状→Component→File→Test→Rollback |
| F08 | Final Acceptance | S7-01..06 | 同時運用・負荷・障害・復元PASS |

## 横断受入：GitHub非依存

F01〜F04/F06に対しS1-04で実コードのGitHub必須依存を確認し、F08のS7-01/06でGitHub遮断時の起動・Web/Bot・認可付きStorage・受領済みKB検索/Current・ローカル復旧を実PC検証する。F05はTGS外部通信/有界spoolと復帰後読戻しの別証拠。Githubの開発管理とKB履歴のSource provenanceは維持。完成後Private化は実行/読戻しまでPENDING。

## デバッグ対応表に必須の列
TASK_ID / COMPONENT_ID / SYMPTOM / DEPENDENCIES / PROCESS_OR_SERVICE / SOURCE_PATH+SHA / CONFIG (redacted) / DATA_STORE / LOG_ID / TEST_COMMAND+EXIT / ROLLBACK / OBSERVED_STATUS / OWNER。

実機の内部情報とセキュリティ証跡は公開GitHubへ貼らず、閉域で保管。GitHubには秘密のない要約と証拠照合IDを置く。

## 2026-10-30 汎用アプリ責務の実装対応

F02/S2の個別アプリ管理は `scripts/gserver_apps.py`（アプリ所有Compose→`gace-app-<name>`）。Core/API/Storageの既存 `scripts/gserverctl.py` とプロジェクト・volumeを分離する。検証は `tests/test_gserver_apps.py` と `tests/test_gserver_apps_smoke.py`、実機受入は `scripts/smoke_gserver_apps_host.sh` → `scripts/smoke_gserver_apps_host.py`。操作・症状・復旧対応は [APPS_RUNTIME](APPS_RUNTIME.md)。F05のBotログspool/Gateway連携は保持するが、F02の独立アプリ稼働を証明しない。F01/F06のWindows起動復帰とF04/F05/F08の最終受入は別Gateとして維持。

## 2026-11-04｜全project共通domain設定（F02/F06/F07）

入口 `scripts/gserver_domains.py`、owner/zone/endpointとbindingのprivate JSON → hash付きdesired revision → project/Tunnel別ingress。新project追加/旧host併存切替/取消済みzone拒否/認証保持/競合防止/復元は `tests/test_gserver_domains.py` の19件、全380 tests PASS。`scripts/verify_gserver_domains_host.py` は既存cloudflaredのnetwork noneで架空domainのnative設定/新旧route/未知host404/rollbackと既存container不変PASS。本番DNS/Tunnel/Access/callback反映は未実施、live=NOT_VERIFIED。コードを変更せず任意projectのdomain設定を差替え可能。[操作/境界](APPS_RUNTIME.md#project-domain-configuration)。

## 2026-11-04｜販売Botの所有・接続Gate更新

F02主対象は `seigo-gace/create-videobot`（Master明示）。GATE/GroupBotと取り違えない。既存Draft PR #1固定Source `ae8a2385` の実bootstrap/adapterを新規の専用Core cloneへ接続し、認証/重複/409/Owner拒否/再起動後SQLiteと既存Core/Storage/全container不変がPC PASS。実Sales/Telegram/支払稼働は未受入。入口 `scripts/smoke_videobot_integration.py`、境界回帰 `tests/test_videobot_integration.py`、手順/残Gate [APPS_RUNTIME](APPS_RUNTIME.md#videobot-consumer-contract-acceptance)。VideoBot37 Node tests、Gserver361 Python tests PASS。実装 `807af80` の [CI Run 41677777575](https://github.com/seigo-gace/G-ACEserver/actions/runs/41677777575) はPython/Core/Bot Docker各step SUCCESS（VideoBot consumerの実接続はPC証拠）。元stagingの共有external networkは現app管理で意図どおり拒否、無断で例外を追加しない。Tumblrの実OAuth/adapterとF04は別の残Gate。

## 2026-11-04｜PC実測による更新（後続の11/02表より優先）

- **F02:** 統合Source `83b7060` の4アプリmodule SHAと稼働image内のSHAを照合し一致。再buildなしで既存 `bot_acceptance.verify(Controller())` の認証分離・202/duplicate/409・stop/start後SQLite保持・実Source一致がすべてPASS。独立apps既PASSは再実行なし。実Bot/Tumblr個別機能と旧imageへの復帰は別の未受入Gate。
- **F01/F03/F06:** WSL systemd/Docker/containerd稼働、認証付きCore ready/files、SQLite quick_check、G:隔離一時dirでの保存/更新/ゴミ箱/復元/SHA/容量確認PASS。Windows reboot、USB断、容量枯渇、遠隔backup/復号/隔離復元は未実施。
- **Docker操作の逆引き:** `scripts/local_docker.py` → `gserverctl.py` / `gserver_apps.py` / recovery / WSL audit。`tests/test_local_docker.py` はroot/既存socket権限/従来sudo fallback/明示local socketを検証。新規3件を含むPC全352 tests PASS。実装 `739a78d` の [CI Run 41673993937](https://github.com/seigo-gace/G-ACEserver/actions/runs/41673993937) はPython回帰/Core Docker/Bot Docker全step SUCCESS、PC証拠とは区別。
- **優先順位:** 今回の直接Master指示によりKB/F04は後段。既存appの利用・データ保護・通信保護・復旧を優先し、正式認証を要するGateway/P015/Cloudflare/Vault/Terminalは所有契約を確認して進める。ローカルBotログ受入だけで実appや通信保護完成としない。[詳細・実行記録](../CURRENT.md)。

## 2026-11-02｜F01〜F08実行マッピング（現行PR #15 Source基準）

この節は**新しい仕様・追加Stage・再実装指示ではない**。既存F01〜F08／S0〜S7・46タスクを、現在の Source → 依存 → 実証 → 未達 → rollback に結び直す。各Gateの「Source実装」「GitHub CI」「Owner PC Runtime」「外部Provider往復」「復旧」を**別々**に判定する。未実施をPASSにしない。上の初期表に残る古いUI必須・Docker未導入という表現より、最新FINAL_ACCEPTANCEと実機証拠を優先する。

### 現時点での正本と証拠区分

- GitHub実装候補：G-ACEserver Draft PR #15、branch `chat/gserver-generic-app-runtime-20261030`、Source/CI照合に使用したベースSHA `5d281f5209ce0b808a0cc58d8a9969836130f877`（本マッピング追加前）。以後の文書専用CommitでSourceの受入実機SHAを更新したことにはしない。mainへの統合やMaster PCへの反映を意味しない。PR #24/#25はこのbranchへ統合済み。別途正本Repoの実機HEADが更新された場合は照合し直す。
- **CI実測**：[Actions Run 41423817040](https://github.com/seigo-gace/G-ACEserver/actions/runs/41423817040)（PR #15 HEAD `5d281f52`）：Python 349/349、Core Docker health/auth、Bot Dockerの202保存・202再送・409競合・権限分離・restart後SQLite保持がPASS。**実行HostはGitHub runner**でありMaster PCではない。
- **Master PC実測**：2026-11-01のOwner返却で`PC_GENERIC_APP_RUNTIME_SMOKE`、`INDEPENDENT_APP_LIFECYCLE_DEMO`とも`VERIFY=PASS/EXIT_CODE=0`。独立アプリ二件の共存・停止分離・永続化・config rollback・Core/Storage無干渉を受入。ログは現行統合HEADそのもののBot installを証明していない。Owner PC の `BOT_GSERVER_LOCAL=PASS` は**未提示**。
- **既存局所実機証拠**：Coreの認証/Storage ready/files、G:の主要な操作、JP/KR VPN隔離試験などはPR #15設計・CURRENTに個別記録あり。ただしF01〜F08の総合受入とは別。Gateway→P015 Telegram raw/index一致、F04 search/current切替、F05 encrypted restore、完全自動起動/PC障害復旧は未受入。
- 個人Host IP、Secret、認証値、実データや非公開ログはこの公開文書に保管しない。公開面には安全なPASS識別子/Run/Commitのみ残す。

### 機能・責務・Source・受入の逆引きマップ

| F要求／既存Task | 実体・責務境界 | 主要Source／実行口 | 試験／証拠 | いま未達の完成条件 |
| --- | --- | --- | --- | --- |
| **F01** S1-02/07, S2-02/04 | Windows→WSL systemd→Docker Engine/Compose。C:最小、D:WSL ext4、他runtime非破壊 | `scripts/audit_f01_wsl_boot.py`、`scripts/windows_f01_boot_readonly.ps1`、`scripts/gserverctl.py`、`deploy/` | `tests/test_audit_f01_wsl_boot.py`、`tests/test_windows_f01_boot_contract.py`；既存WSL/Docker実機PASSは局所 | **Windows起動→WSL→Core/Bot/Apps自動復帰、重複runtimeとC:/D:容量の実測**が未閉鎖 |
| **F02** S2-03/04/05, S5-01 | Core/APIと独立アプリは分離。BotイベントはCoreのローカルAPI→SQLiteへ永続化。Botの機能そのものをCoreへ移さない | `app/gserver.py`、`app/tgs_bridge.py`、`scripts/gserverctl.py`、`scripts/gserver_apps.py`、`scripts/gserver_bot_ready.py`、`scripts/bot_acceptance.py`、`scripts/demo_independent_app_lifecycle.sh` | `tests/test_runtime.py`、`test_bot_acceptance.py`、`test_tgs_bridge.py`、`test_gserver_apps*.py`。Owner PC apps smoke/demo PASS、PR #15 CI Bot Docker PASS | **Owner PCに統合HEADを反映してBot認証・DB永続化・リリース復旧を検証**。実Bot/Tumblr個別機能は別ownerで採用判断、管理Web UIは不要 |
| **F03** S3-02..05 | G:認可付きStorage。F:はDev KB原本として読取保護。Docker imageへ個人データ内包しない | `app/storage.py`、`app/storage_mutations.py`、`scripts/gserver_files.py`、`scripts/f03_storage_mount_audit.py`、`scripts/wsl_mount_kb_f_readonly.py` | `tests/test_storage*.py`、`test_gserver_files.py`、`test_f03_storage_mount_audit.py`。G:基礎操作のMaster PC PASSは個別保全 | **USB切断、容量上限、再接続、部分転送後の回復、既存データ非損失**の異常系は未閉鎖 |
| **F04** S4-01..06 | 既存 `gace-dev-kb` のMVS(BM25/Vector/Hybrid/KG/MCP)、ModuleCatalog、単一Current、履歴/rollbackを**再実装せず利用** | `app/kb_source.py`、`scripts/gserver_kb.py`、`scripts/gserver_kb_mount_probe.py`、`scripts/windows_existing_kb_mcp_acceptance.ps1`。原本F: | `tests/test_kb_source.py`、`test_windows_existing_kb_mcp_contract.py`、`test_gserver_kb_mount_probe.py`。Source verifierは既存だが `KB_SEARCH_E2E=NOT_VERIFIED` | **F:現物SHA/数量→既存検索(MCP含む)→Index/ModuleCatalog受領→単一Current切替→復旧E2E** が未実施 |
| **F05** S5-02..06 | Gserver Bot/Web/KB Producer→**既存**Gateway `/internal/events`→別Host TGserver ZERO P015（G002）→Telegram raw/検索。バックアップは別データ責務 | `app/tgs_bridge.py`、`scripts/gserverctl.py`のbot-gateway-config/canary/retry、`docs/architecture/BOT_TGS_BRIDGE.md`。TGserver/Gateway owner Sourceは別Repo | `tests/test_tgs_bridge.py`、`test_bot_acceptance.py`、PR #15 CI Bot Docker。Gateway 202は**受領のみ**でTG raw/index PASSではない | **正式認証のPC→Gateway→P015 raw/index/event_id照合**と、ファイル/KBログ**暗号化スナップショット→実送信→ダウンロード→SHA/復号→隔離復元**。現状バックアップ完成ではない |
| **F06** S6-01..06 | Windows/WSL/Docker安全運用と保護app VPN、cloudflaredは保護namespaceへ。監視・復旧・資源は独立Gate | `scripts/gserver_vpn.py`、`scripts/verify_vpn_live_host.sh`、`scripts/gserver_cloudflare_discovery.py`、`scripts/gserver_connection_readiness.py`、`scripts/gserver_recovery_check.py` | `tests/test_gserver_vpn*.py`、`test_verify_vpn_live_host.py`、`test_gserver_recovery_check.py`。JP/KR局所Owner PC PASS、Tunnelの実稼働・速度未受入 | **正式Cloudflare/Vault認証・隔離接続、漏洩防止、回線断/再起動でのfail-closed復帰、CPU/RAM/IO・必要速度の実測** |
| **F07** S0, S7-05 | 症状→実サービス/port→Source→ログ/受領ID→再現テスト→rollbackの責務マップ | **このファイルが入口**。`docs/architecture/CONFLICTS.md`、`docs/CURRENT.md`、`scripts/runtime_evidence.py`、`scripts/gserver_recovery_check.py`。共通Terminalは別Host/別ownerの実行経路 | このマップのSource/readback、PR/Issue/CI/PC証拠を別々に保存 | 本表は**SourceとGateの対応まで**。PC実サービスの実ポート・ログ・障害復旧receipt相関は実測後に秘匿した形で追記が必要 |
| **F08** S7-01..06 | F01〜F07を**実PCで**同時受入。GitHub切断下の通常運用、rollbackと永続データ復旧。完成後Repo Private化 | `scripts/verify_pc_runtime.sh`、`scripts/gserver_recovery_check.py`、`scripts/smoke_gserver_runtime.sh`、各F別検証器 | GitHub CI 349 PASSはSource側の証拠のみ。Owner PC F02 apps局所PASS、Core/Storage局所PASSを保全 | **統合障害試験、Windows/WSL/Docker起動復帰、GitHub遮断試験、F04/F05実復元、秘密/個人データ監査、Repo Private化・readback** |

### 依存関係と作業順（新規サービスを作らない）

1. **F02を先に閉じる**：現行PR #15 HEADとMaster PCデプロイSourceのSHAを突合→既存 `scripts/gserver_bot_ready.py --install` のOwner PCゲート（必要時のみ）。既にPASS済みのapps-only smoke/demoは再試験しない。ここでローカルBot/Storageを稼働可能として、外部TGS/Cloudflareの未完成と混同しない。
2. **F05 Producerの既存正式API接続**：TGserver P015の既存登録/受領口→Gateway destination・sourceId・eventId・`internalDataPolicy`→Vault/Cloudflare Accessの所有・認証を確認→合意済みG-ACE zone内の保護されたPC Producer canaryを送信→TGserver rawおよび検索Indexの同じ相関IDを読戻す。Gateway 202だけで合格にしない。Astera zone流用、Providerの無断変更はしない。
3. **共通Server TerminalのGserver第2Host**（F02/F06/F07開発運用横断、製品F番号を増やさない）：既存server-core Actions→Gateway→Receiver→Host Writer→Result Sinkの契約を維持し、正本Control #10のHost target分離計画に従ってGserverの登録/認証/結果返却へ接続。固定Git-only別Terminalは採用しない。P015/Gateway/Vaultの確認順を飛ばさない。ContaboとのHost/Domain/Secret分離を守る。
4. **F06の保護と本番運用**：JP/KR試験局所PASSと正式Cloudflare/Vault実接続、Fail-closed、自動復帰、媒体別速度・漏洩検証を別々に終了させる。VPN安全証拠を外部接続認可の代用にしない。
5. **F04・F05の重いデータ責務**：F:既存KBのCurrent+検索+履歴+rollback、続いてTGSの既存正式ファイル/バックアップAPIで暗号化upload/readback/isolation restore。未実装のTGS vNext APIを稼働済みと呼ばない。
6. **F01/F03/F06/F07/F08横断**：電源/USB/ネットワーク障害、リソース/速度、GitHubオフライン、原本/volume回復を既存試験へ通し、最終ACCEPTEDと別にRepo Private移行/読戻しを実行。

先に申告した**16〜25ターンは初期見積もりで確定ではない**。内訳：F02 Bot 2、Producer P015 2〜3、共通Terminal 2〜3、VPN/Cloudflare/Vault 2〜3、F04 3〜5、F05 Backup 3〜5、F01/F03/F06〜F08統合 2〜4。各1ターンはSource→検証→修正→証拠の作業単位。利用者の同意/Provider Gate、現物の性能/障害で変動する。

### 障害を根元から追う最小対応表

| 症状／不達 | まず見る所有層と証拠（秘密除外） | 使う既存検査／復旧境界 |
| --- | --- | --- |
| Windows再起動後にGserverが使えない | F01 Windows起動→WSL systemd→Docker engine→Gserver Coreとport→状態DB | `scripts/audit_f01_wsl_boot.py`／`scripts/gserver_recovery_check.py`。勝手に複製Docker/WSLを起こさない |
| Web/Owner APIで401/503 | F02認証・F03マウント：`app/gserver.py`→`app/storage.py` | `scripts/gserverctl.py status`、既存Storage readiness。401を起動失敗と混同しない |
| アプリのみrestart/rollback失敗 | F02 `gserver_apps.py`/各app所有Compose→独立volume→health | `tests/test_gserver_apps.py`、Owner PC既存smoke。Core/Storageを停止せずapp単位で検証 |
| Bot `202`だがTGSで見つからない | F02ローカルSQLite→F05 Gateway 202→Delivery/Outbox→P015 raw/index | `/bot/queue`、`bot-gateway-canary`、既存Gateway/TGSのeventId照合。同じIDを新IDに変えて重複送信しない |
| Bot retry後に送信数が合わない | `app/tgs_bridge.py` のlease generation／sent receipt／SQLite WAL | `tests/test_tgs_bridge.py`、Ownerだけの`bot-retry`。受信側202と最終配送は別 |
| KB CurrentはACTIVEでも検索できない | F04 F: mount→Current/receipts→既存MVS index/mcp/search | `scripts/gserver_kb.py`、既存Windows MCP受入。F:原本を上書き・新Index再実装しない |
| VPN/Cloudflare接続不可 | F06 実kernel guard→WireGuard JP/KR→DNS/IPv6→Tunnel/Access→Gateway | `scripts/verify_vpn_live_host.sh`、`gserver_connection_readiness.py`。直接Public IPへfallbackしない |
| バックアップはあるが復元できない | F05 manifest/鍵→遠隔object receipt→SHA/AEAD→独立Dir | TGS既存正式API readbackと隔離復元。現状Source・Runtime完成証拠なし、原本への上書き禁止 |

**データ境界**：D:既存WSL ext4正本／G: authorized storage／F: KB原本／Docker named volumeには認証とSQLite spool／TGserverは別Host。Contabo Gateway/Receiver権限はGserver PC操作権限ではない。GitHubは開発・配布用であり本体の通常稼働に必須としない。
