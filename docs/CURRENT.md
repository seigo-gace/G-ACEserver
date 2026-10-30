# Current priority (2026-10-30 JST) — Gserver is a generic PC server, not a Telegram product

**Master's latest scope:** Gserver on the user's Windows 11 / WSL Ubuntu PC provides Docker/Compose, independent app lifecycle, local API, G: Storage, safety/recovery and optional secure network egress. Telegram Bot and Tumblr are separate app projects, not Gserver Core features. TGserver is for logs/backup as an optional separate service, not a Bot runtime prerequisite. Never change the existing shared Webhook Gateway internals without Master's explicit service-owner instruction. Do not change Contabo/Astera or Astera-owned domains for Gserver. VPN is a design option to improve source-IP privacy, not a blanket requirement that blocks locally usable server functions.

**Observed PC runtime (Master's terminal, 2026-10-30):** existing immutable gace-gserver-gserver-1 container healthy, 127.0.0.1:18765/health HTTP 200; G: mounted; Owner auth configured; authenticated /ready and /files HTTP 200. This is proof of existing local Core and Storage availability, not Windows reboot recovery, general app launch, remote ingress, backup restoration, or all F01-F08 acceptance. Preserve the running release, G:/F: originals, Docker volumes and pending Bot SQLite events.

**Next immediate development:** complete the generic app Compose lifecycle independently of Core, validate one real app-owned Compose config on the PC, check Windows-side access and reboot startup separately without installing unapproved scheduled tasks, then close only those acceptance gates supported by real evidence. The new local-only app manager is scripts/gserver_apps.py; its isolated source/tests are in PR #15 and must not be represented as deployed. App start uses local images only and disallows privileged/host/public/external resources by default. No new Bot, gateway/TGserver route or Cloudflare dependency is required for normal local app hosting. KB/F04 and future commercial features remain deferred, not deleted.

**Source/CI/Runtime distinction:** On branch chat/gserver-generic-app-runtime-20261030, new app controller and eight offline unit tests passed in the isolated CHAT test container. The user's PC has not yet fetched or executed that branch, and no genuine app was started/stopped by this change. Existing PC runtime remains the earlier verified immutable image. Do not pull/reset the user's existing local non-main working branch or overwrite Docker runtime merely to pick up this code.

---
## Historical evidence (superseded priorities below)

## 2026-10-28 Codex / Bot PC受入・二分割の適用

- **Owner / Source:** Issue #9 comment 6465378786を適用。作業branch `codex/bot-pc-acceptance-20261028`。GPT CHAT修正HEAD `6dbc0d5238b1eeeb4d0524f2c2c58f5acefbe8ef`をclean checkoutへfast-forward統合。Codexは `app/tgs_bridge.py` / `tests/test_tgs_bridge.py` を編集していない（修正branchとの差分0）。Codex修正commit `6d6b9dc`。
- **修正:** Docker contextが必須importの `kb_source.py` / `tgs_bridge.py` を除外していたため、明示allowlistへ追加。既存KB機能の開発再開ではなくアプリ起動依存の修復。Owner認証ファイル設定を全Compose profileへ共通化しstorage profileの重複注入を除去。受入スクリプトはsudo拒否を `DOCKER_SUDO_AUTH_REQUIRED` と秘匿診断し、Bot検証失敗時には旧image/access/storageへ復帰（初回は停止、volume保持）。
- **実行可能な受入:** `scripts/bot_acceptance.py` を `gserver_bot_ready.py --install` に接続。実loopback 18765のBot/Owner認証分離、202→duplicate→409、実image/module SHA照合、SQLite該当行のfingerprint/payload保持、既存Gserverだけstop/start後のduplicate/409を検証。秘密はprocess内のみ、proxyを使わない。合成correlation IDのみ出力。これらのDocker実行は未達。
- **Local verification:** このWSLでbridge16、runtime41、deploy contract4、新acceptance8、計69 tests PASS。新8件には許可済みDocker contextだけを一時再現した実import、全profileのOwner設定、sudo診断秘匿、停止失敗時のstart試行、再起動後replay消失の拒否、受入失敗時rollbackを含む。Controller/Docker境界のmockは実機Docker PASSと区別。Compose isolated/loopback/storage 3構成config PASS、git diff --check PASS。CI=NOT_RUN。
- **PC Runtime (実測):** `python3 scripts/gserver_bot_ready.py --install`を実行し、tests後Docker preflightでexit1。修正後診断=`DOCKER_SUDO_AUTH_REQUIRED`。Docker build/activation/Bot restartへ到達していない。既存loopback `/health` HTTP200、`/bot/queue` HTTP404でBot新版の受入は未完了。旧ローカルrelease recordにはimageがあるがdaemonによるimage再照合は未実施。既存Podman/Redis/site_total/btpanelはactive。docker/containerdの各store空き2GiB以上をread-only確認。既存原本・サービス設定・VPSは無変更。
- **Gateway / TGserver / Telegram:** Gateway正本Internal Event APIとTGserver ZERO integrationを読戻し。P015/G002はsource登録済みという契約を確認。private Gateway設定/到達性/202、P015 live topic audit、TGserver配送、Telegram raw、中央Reader検索相関はいずれもNOT_VERIFIED。Source文書はLive証拠ではない。資格情報を別Projectから流用せず、VPS deploy/Topic作成/新Reader/新Workflowは実行していない。
- **Rollback / Exact Next:** sudo本人認証の境界を解消し、既存WSL checkoutで `sudo -v && python3 scripts/gserver_bot_ready.py --install` をforeground実行。端末別sudo cacheなら同じ端末で行う（パスワードをチャットへ渡さない）。成功後に既存private Gatewayの正規設定・接続確認→P015 live state read-only audit→同一event IDのGateway受領/TGS/raw/中央検索→停止再送の実証。VPS変更が必要なら既存Owner権限へ戻す。F01-F08は未完了。追加AI・定期タスクなし。

# CURRENT｜G-ACEserver
## 2026-10-28 Master優先変更：KB停止、GserverをTG Bot受け皿+既存TGserver ZEROへ最速実装

- **Master最新指示:** 「KBは後回し、早く使えるように。もうすぐTGのBotを実装するためTGserverまで」。F04新規作業はここで保留。F02/S5（Bot実運用、既存TGS連携）を先行。妻PC・SMB・追加UIは対象外、既存F:read-only接続/原本は維持。
- **既存ソース再利用:** TGserver repo `seigo-gace/TGserver` の既存ZERO v1.5 `POST /ingest/bulk` と中央Reader、Webhook Gateway既存 `POST /internal/events` およびdestination `tgserver-zero-bulk` を調査。新規TGserver/重複Gateway/公開Bot集約を作らない。Gateway 202は durable Event/Delivery/OutboxでありTelegram raw到着ではない。秘匿値はGitHubに登録しない。
- **TGserver source登録:** G002（旧P011-P014）にGserver専用 `P015` を登録、P001-P014は無改変。 `storage-registry.json`・`src/storage/registry-config.test.ts`・ZERO central Reader `.github/tgserver-zero-project-map.json`・Reader test/Docs を更新。Source commits `9c48b4e4a9c4afa9dcec8e0faac0d17aa1a056ad` / `56d51af13aee91f85d02cae0f692048b7ce7f323`。**TGserver CI実Run 40659601633・40660847744=SUCCESS**。本番VPS配置・P015の5 severity Topicは未確認、topic重複回避のためLive registry/stateの監査前に自動provisionしない。
- **Gserver実装:** `app/tgs_bridge.py`にP015専用、Botの安全な固定運用メタデータのみ受入、SQLite WAL/FULLの耐障害spool（最大5000 outstanding、Idempotency、60秒claim lease、最大20回bounded retry、409/401/422等はblocked、明示bot-retry）および既存Gatewayへの限定HTTPS送信。Botメッセージ本文、Telegram chat/user ID、ファイル、任意URL、秘密は受入拒否。Gatewayの生成receipt IDと送信者event IDを混同しないよう実装修正済。
- **Gserver製品API:** `app/gserver.py`にBot専用Bearerで `POST /bot/events`（ローカルSQLite durable後のみ202、重複202、別内容同一ID409、非設定503）。Owner認証 `GET /bot/queue`（数だけ）を追加。既存API/G:保存と認証境界を維持。送信WorkerはGserverプロセス内でGateway設定ファイルがある場合だけ送信、別常駐System/AIタスクは作らない。
- **Docker/Owner CLI:** `deploy/compose.gserver.yaml`の既存named volumeにBot spool/独立Bot認証位置を追加、`gserverctl` storage profileの旧env注入を修正して重複YAML防止。`gserverctl bot-init/bot-smoke/bot-status/bot-gateway-config/bot-retry`を実装。tokenはVolume内0600、OwnerがGateway URL/tokenをhidden input→Docker stdinで注入（source/CLI argv/GitHubへ埋め込まない）。既存localhost限定18765はそのまま、旧8765を上書きしない。`scripts/gserver_bot_ready.py --install`はテスト→Docker空き容量2GiB以上→既存immutable image build/activate+既存rollback→loopbackだけenable→Bot token生成→実ローカルHTTP入庫→queue確認。任意の大規模新Runtime導入やDocker pruneなし。
- **テストと受入未完:** `tests/test_tgs_bridge.py`14ケース（schema privacy、retry/persist/idempotency/gateway 202 IDs/blocked recovery等）、`tests/test_runtime.py`Bot API追加2ケース + Owner CLI追加3ケース、`tests/test_gserver_bot_ready_contract.py`4ケース。GitHub Source確認済みで、**Gserverのこれら新テスト、Docker image Build/Running HTTP、Gateway 202、TGS VPS raw/index/searchはMaster実機未検証**。これらをPASSとしない。
- **Exact Next:** Master PC WSL既存Gserver checkoutをclean/pull、`sudo -v`が得られる場合に`scripts/gserver_bot_ready.py --install`を1度実行。作業者は非技術者なので1ブロックPowerShellのみ提示。local event 202+SQLite永続+127.0.0.1:18765 を確認したら、既存Gatewayのprivate HTTPS reachability・Credential受入・本番TGserver P015 live topic登録/検索確認へ進む。Hostに権限がなければ機能追加を勝手に止めずSourceを整備して必要な権限/原因を一つに絞る。**最終F01-F08完成と誤記しない**。

## 2026-10-28 F04既存MVS/MCP本番検索回帰の受入Scriptを実装｜まだPC未実行

- **Source実装:** `scripts/windows_existing_kb_mcp_acceptance.ps1` はすでにF:に存在するDev KB原本の `tests/mcp_knowledge_client_e2e.py` と `tests/mcp_reusable_asset_e2e.py` を、既存Windows `runtime/mcp-vector-search/Scripts/python.exe` で順番に起動。新MVS/新MCP server/別受領watcher/新task/new tokenを設置せず、既存ソースを再利用する。`MCP_ENABLE_FILE_WATCHING=false` と Python bytecode OFFを当該プロセスに限定し、最後に環境変数を復元。既存のACTIVE markerとruntime-stateのcommitとKnowledgeUnit countの一致を前提条件にする。結果は `KB_MCP_HISTORY=PASS` と `KB_MCP_REUSABLE_BM25_VECTOR_HYBRID_KG=PASS` を**既存本番プローブが終了コード0**の時だけ出力。生のKB検索結果・例外本文・ローカルパス・秘密を出力しない。Source `881d497742aa3b0ee71ef882a2449812df9eafca`, `ea5a695feb1d29b6813191771b207d8041977b80`。
- **テストSource:** `tests/test_windows_existing_kb_mcp_contract.py`に元Dev KB 2 probes再利用・ACTIVE前提・新サービス/Task/索引作成禁止・構造化結果確認の4 static testsを追加。**この4件とWindows PowerShell parser、Windows MCP本番E2EはMaster PC未検証**。
- **接続順序:** Gserver WSLの`test_kb_source.py`16件・MCP契約4件→`scripts/gserver_kb.py --verify-counts --verify-projection`（read-only実SHA/実件数/720 Markdown byte-exact）→全部PASSかつWindows PowerShell Parse PASSの場合のみ`windows_existing_kb_mcp_acceptance.ps1`→最後に同じF: read-only整合再照合。各Phaseで停止条件を守り、**F:の故障・Current改変時にMCPを起動しない**。MCPは検索ランタイムを実行するため正本ファイル未変更は実測SHA再照合によって検証する。Windows MPC runtimeのキャッシュ/一時状態作成有無は別項目であり無条件NONEと書かない。
- **F04受入:** このテスト成功でも、Gserver新Docker内でMVSが動くこと・F→G移行・TGS連携・復元シナリオの実証までは完了しない。PhaseごとにSource/Host実測を分離し、完了主張をしない。

## 2026-10-28 F04 F:既存Currentの「実件数・実SHA・元Projection」3層照合Sourceへ進行

- **確定したMaster実機:** F: read-only drvfs mount、KB root/原本/検索レコード全て存在、ACTIVE Current marker/state/receipt整合。Current宣言 `Formal=814 / Knowledge Units=720 / Relationships=720 / Cases=160`。まだ本物のMVS検索E2E/復元は未確認。
- **追加実装:** `app/kb_source.py::verify_existing_counts()` は ACTIVE+SHA照合済みのCurrentを前提に、既存F:原本の `formal-kb.jsonl / knowledge-records.jsonl / knowledge-metadata.jsonl / relationships.jsonl / cases.jsonl` を1MiBずつ**read-only**ストリーミングで実件数照合する。ファイル/巨大レコード上限・nofollow/regular-file確認、宣言件数不一致時はfail closed。実件数を照合してからもう一度CurrentのSHA整合を読み返す。`scripts/gserver_kb.py`に`--verify-counts`を追加（自動的に6 source hashを先行確認）。既存`--verify-projection`は元Dev KB `verify_modulecatalog_runtime_projection.py` そのものを利用するため第2検索エンジンは作らない。新Source commits `7e5ca2b951a6bca9b328fbc5303b23dedad60081`, `2514747cf0b49e45d8c1529c4eea49a9dc61db69`。
- **追加テスト:** `tests/test_kb_source.py`に実行データと宣言一致・hashは正しいが件数が異なる改ざん拒否・未ACTIVE拒否を3件追加（旧13→**計16件のsource tests**）。Source commit `f20dcec1d9f382206dfee2cfd2c6c7ed5004acfc`。**新16テストおよび実F:のhash/projectionはこの時点では未実行**。
- **Exact Next Gate:** Master WSL clean checkoutからpullして`test_kb_source.py`16件を実行し、PASS時のみ`python3 scripts/gserver_kb.py --verify-counts --verify-projection`を実行。結果で`KB_CURRENT=ACTIVE_AUTHORITY_HASHED`、`KB_JSONL_CARDINALITIES=PASS`、`KB_EXISTING_RUNTIME_PROJECTION=EXISTING_KB_VERIFIER_PASS`の3条件を検証。これらは**MVS BM25/Vector/Hybrid/KG/MCPの実検索証明ではない**ため、通過したら既存Dev KBのWindows native search probeを再利用するF04 E2Eへ直結する。F:原本を移動/編集/再インデックスしない。

## 2026-10-28 F04 Master実PCでF:接続とCurrent ACTIVE実証｜次はファイル実SHA・既存Projection

- **Master実測:** Windows `F:\\G-ACE-KB` は存在。Gserver checkout `386ab68` にfast-forward、`test_wsl_mount_kb_f_readonly.py` **5/5 PASS**。`scripts/wsl_mount_kb_f_readonly.py` が `mount -t drvfs -o ro F: /mnt/f` を明示一度だけ実施、`F_WSL_MOUNT=MOUNTED_READ_ONLY_VERIFIED` `KB_F_ROOT_VISIBLE=True` `F_WINDOWS_CONTENTS_CHANGED=NONE` `VERIFY=PASS`。続くWSL `gace` 利用者の `scripts/gserver_kb_mount_probe.py` は `F_KB_MOUNT_STATE=F_KB_ROOT_READABLE` `F_MOUNT_FILESYSTEM=9p` `KB_REPO_PRESENT=True` `KB_FORMAL_PRESENT=True` `KB_ACTIVE_MARKER_PRESENT=True` `KB_SEARCH_RECORDS_PRESENT=True` `F_SOURCE_MODIFIED=NONE` `VERIFY=PASS`。F:はGserverから**読み取り専用で参照できる状態になった**。
- **ACTIVE Current実測:** `scripts/gserver_kb.py` `VERIFY=PASS` `KB_CURRENT=ACTIVE_AUTHORITY_CONSISTENT` `KB_CATALOG_COMMIT=68e7d643d0e6931e646fd8895d189fb4e1ee337d` `KB_TOTALFORMALRECORDCOUNT=814` `KB_KNOWLEDGEUNITCOUNT=720` `KB_CASECOUNT=160` `KB_RELATIONSHIPCOUNT=720` `EXISTING_WINDOWS_MVS_PRESENT=True`。marker/state/receiptのACTIVE・commit・hash申告・件数整合はPASS。**宣言される件数であり、全実ファイル/索引/MCPの実行証明ではない**。
- **残未検証:** `KB_EXISTING_RUNTIME_PROJECTION=NOT_VERIFIED` `KB_SEARCH_E2E=NOT_VERIFIED` `KB_CURRENT_CUTOVER=NOT_PERFORMED`。次は既存のF:ファイル6つの実SHA検査と、既存Dev KB `verify_modulecatalog_runtime_projection.py` を利用した720件Markdownの byte-exact 検査。既存Windows MVSプロセスやMCP検索は、その後の実行環境確認とする。ユーザーからリアルで渡されたログ以外をPASSと誤認しない。
- **安全:** F:/G:既存データ・Windows設定・SMB・Firewall・Docker/Compose・Current切替は変更していない。WSL /mnt/f の一時 read-only mountのみ変更した。妻PCは開発対象外。F04は部分E2E PASS、製品全体F01-F08は未完成。
 
## 2026-10-28 Windows F:は存在、WSL /mnt/fは不在｜明示的なread-only DrvFs受入を実装

- **実測 (Master):** Windows PowerShell `WINDOWS_F_DRIVE_PRESENT=True` / `WINDOWS_F_KB_ROOT_PRESENT=True`。Gserver main `2037812` をpull、`test_gserver_kb_mount_probe.py` 8/8 PASS、`test_runtime.py` 36/36 PASS。Gserver診断 `F_KB_MOUNT_STATE=WSL_F_PATH_MISSING`、`F_SOURCE_MODIFIED=NONE`、`VERIFY=PASS`。そのため `KB_CURRENT_INSPECTION=SKIPPED_F_MOUNT_NOT_READY`。**Windows原本とディスクは存在。WSLにF:接続が欠けているだけ。** 既存Dev KB Current/MVS/ModuleCatalogはまだ実測していない。
- **実装:** `scripts/wsl_mount_kb_f_readonly.py` はユーザーが明示的に一度実行したときのみ、WSL rootで、空/不存在で安全な`/mnt/f`のみに `mount -t drvfs -o ro F: /mnt/f` を実行する。Linux `os.ST_RDONLY`を検証し、`G-ACE-KB` rootの存在確認。書込可能な既存mount/別mountやsymlinkを拒否、25秒timeout、今回だけに新規mountした場合の失敗時umountと空mountpoint rollback、`fstab`/`wsl.conf`/F:内容/既存G:データの変更なし。該当コマンド以外の自動/常駐マウントは作らない。Microsoft Learn公式WSL DrvFsの外付けNTFS Windowsドライブ接続方法に従う。`tests/test_wsl_mount_kb_f_readonly.py`に固定ドライブ、ro、root/既存mountガード、限定rollback、持続設定禁止、timeoutのsource/AST testsを追加。Source commits `c8a26d475e9b768a7ca63d17ff8d9968a477dcf2` / `9a000a85986c686c701235d9c50efb76476bc3d9`。**新5テストとroot mountは未実機実行**。
- **Next:** Windows F:\G-ACE-KB existenceを再確認 → WSL repo clean/pull/新5テスト → Ownerが同PowerShellコマンドでrootのread-only drvfs attachを明示的に実行 → gaceユーザーで `scripts/gserver_kb_mount_probe.py` → `scripts/gserver_kb.py` read-only。後者が`NOT_ACTIVATED`でも旧formal baselineが別途存在し得るのでKBを勝手に移設/再索引しない。結果を基に既存MVS/Currentの正式受入に接続。F04はSOURCE_IMPLEMENTED/PC_F_MOUNT_GATE_PENDING、F03の以前の27テスト+実G:E2E PASSは保持。妻PC/SMB開発は無効のまま。

## 2026-10-28 F04実PC13/13 PASS、F: WSL非マウント→原因識別と認証付き参照APIを実装

- **Master実測:** WSL Git checkout `00a2e50` fast-forward、`test_kb_source.py` **13/13 PASS**。続けて `scripts/gserver_kb.py` は `KB_ERROR=KB_F_MOUNT_UNAVAILABLE`、`F_SOURCE_MODIFIED=NONE`、`CHANGES=NONE`、`VERIFY=FAIL`。`set -e` で後続操作なし。**Dev KB破損/消失の証拠ではなく、WSL上で `/mnt/f` がmountとして確認できない**ことだけを示す。Windows F:自体の存在は未検証。F:原本を勝手に移動・マウント・上書きしない。
- **今回の実装:** `scripts/gserver_kb_mount_probe.py`（読取専用）にWSL mountinfoの**完全一致マウント位置**、実`os.path.ismount`、既知Dev KB root/正式 corpus/ACTIVE marker の固定パス確認を実装。`tests/test_gserver_kb_mount_probe.py`に8検証例（mount root欠落/未mount/正常mount/他mount誤認拒否/symlink/資料欠落/不正root等）追加。WindowsとWSLのFを別証拠として扱う。Source `927ca1ac81963d21614beb34f305f6f3123a2c9c`。静的source readback OK、**新8テストとWindows/WSL実行はまだ未検証**。
- **F04製品API接続:** `app/gserver.py`に認証必須の `GET /kb` を追加。`GSERVER_KB_ROOT`で明示されたKBの**マウント済みrootだけ**を対象、設定なし/未mountは503、Current検証不一致は503、成功はstatusと3つの既知状態boolだけ返し、KB本文/承認token/hash/パスを返さない。旧API・G:保存・root/ready/health判定を変えず、`/kb` に疑似検索PASSを返さない。`tests/test_runtime.py`に新3テスト（認証/未mount、成功状態で情報漏えいなし、Current失敗時503）。Source commits `c288ff3b9e5762fadb957578d9d80f24983cb67f` / `c5522ff7a15b4bf5dc80ccdb27fbabb4a9cfbf27`。**Dockerへの適用・新APIの実Host応答は未検証**。
- **次の実証ゲート:** Windows側 `F:\` と `F:\G-ACE-KB` の存在だけをread-only確認。同じコマンドでWSL側最新Gserver tests（mount probe8/KB13/既存runtimeとAPI）、`scripts/gserver_kb_mount_probe.py` を実行。WSL mount非可視ならF:の実所在とWindows側媒体アクセスを先に確定し、無断の `mount` やF:データ移設はしない。既存 KB MVS/KG/MCP/復元E2Eは F04 未完了のまま継続。

## 2026-10-28 F04 Master実機 Python検証で2件失敗 → ACTIVE模擬fixture修正

- **Master WSL実測:** `git pull --ff-only` で `5433dd8` へ更新後、`python3 -m unittest discover -s tests -p test_kb_source.py -q` が**12 tests中 1 FAILURE, 1 ERROR**。該当: `test_existing_projection_probe_is_opt_in_read_only` が `KB_PROJECTION_CORPUS_MISSING`、`test_projection_timeout_fails_closed_without_reporting_pass` が同エラーのため期待した `KB_PROJECTION_VERIFIER_TIMEOUT` に進めなかった。**テスト用のACTIVE模擬Currentにrecordsディレクトリを作り忘れたことが原因**。F:本物の検査は`set -e`により未実行であり、F:原本や実KBの破損を示さない。
- **Source修正済:** `tests/test_kb_source.py` の `active()` fixtureで `modulecatalog-reusable-current/records` を作成。既存テストのtimeout/既存元Verifier呼出まで到達できるようにした。さらに逆にrecordsが欠落した場合はverifierを呼ばず`KB_PROJECTION_CORPUS_MISSING`で拒否する新テストを追加（12→**13 tests**）。Source commit `166727539dc7c9d5cd708c4273fe749913f259a2`。GitHub readbackでfixture・テスト数・既存Verifier未再実装・read-onlyを確認。ただし**新13 testsはMaster実機未再実行でありPASSと称しない**。
- **Next (止めずに接続):** Master既存WSL checkoutをclean確認→pull --ff-only→新`test_kb_source.py`を実行。合格した場合に限り`python3 scripts/gserver_kb.py`でF:の実際のCurrent/正式KB状態をread-only取得。Currentが存在しない場合は失敗を繰返すのではなく既存Dev KBの配置/プロセスの現実に合わせ、Gserver F04検索・受領/Current統合の実装へ進む。妻PC・SMB関連は引き続き除外。

## 2026-10-28 F03 G:実機E2E PASS → F04既存Dev KB統合Source実装

- **F03 Master実測:** source 342334e までfast-forward後、storage系 unittest 22件PASS、既存ファイル転送 unittest 5件PASS。G:内の新規隔離試験フォルダーで put, hash, replace, trash, restore, get, quota 全工程PASS、BYTES_VERIFIED=1572900、USER_FILES_MODIFIED=NONE、SMB_FIREWALL_CHANGED=False、VERIFY=PASS。従来のF03読み取り・書込み機能に加え、可逆更新・復元・容量確認の実機統合を確認。USB切断/長時間/容量枯渇試験等は未完了なのでF03全体をACCEPTEDとはしない。
- **F04実Source:** 既存 authoritative Dev KB = seigo-gace/gace-dev-kb（main source f7ed3958、ModuleCatalog generalized receiverはDraft PR #3 のため現在PCでのACTIVEを推測しない）。mcp-vector-search 4.1.14、既存のBM25/Vector/Hybrid/KG/MCPを再実装しない。既存Windows runtime checkerからF:権威ファイル配置とACTIVEマーカー→runtime-state→receipt→6つのSHA256正本→Current Markdown展開検証の受入契約を確認。
- **実装追加:** app/kb_source.py は既存F:/G-ACE-KB（WSL /mnt/f/G-ACE-KB）のCurrent authorityをread-only検査し、JSON/リンク/commit/ACTIVE/schema2/hash申告/件数の不一致にfail closed。scripts/gserver_kb.py はCLIでDefault簡易readback、--verify-hashesは6ファイルSHA実読、--verify-projectionは既存Dev KBの verify_modulecatalog_runtime_projection.pyをread-only Pythonで実行して再使用。元Dev KBのPowerShell health commandはreceive.lock等を作成するため、Gserverから自動起動しない。既存MVS/受領/Activation・インデックスは変更しない。docs/architecture/DEV_KB_F04_BRIDGE.mdを追加。
- **テストSource:** tests/test_kb_source.py 12件で、Current不存在/ACTIVE照合/正本改ざん/receipt矛盾/activation journal残留/symlink/不正件数とhash/非変更/元verifier再使用/欠落/timeout/未ACTIVE拒否を定義。GitHubでsourceとテストをreadbackしたが、**新F04 testsとF:現物状態はまだMaster実機未検証**。Source commits d9f74bdbee576716dd0fb24130a5eddefa682c43, c205a562bb343d8e8b6217b20e09b42256f3b0b3, 87fc3ba253f2b4d87a953895e97d9755197227dc, 24f0035415ac6ce5c1377dcd080ee4c11eb7ec84, 0781368c4cedbdb73ef09bfdac74d23c1e966470.
- **Exact Next:** MasterのWSL Gserver checkoutをpull --ff-onlyして test_kb_source.py（12件）を実機実行、PASS時だけ scripts/gserver_kb.pyでF: source status read-only取得する。現在のMVSがF:で未ACTIVATEDでも「移行済み」としない。実現物/Current状態を踏まえ既存F:原本保護のままDev KBのMVSリグレッション・ModuleCatalog受領/ACTIVE・ロールバックへ進む。妻PC/SMB/FWは現スコープ外。
## 2026-10-28 F03ストレージ作業を継続｜可逆更新・削除・容量管理＋永久削除を安全確認付きで実装、13件LOCAL PASS

- **追加Source:** `app/storage_mutations.py` の `purge(store, restore_id, sha256, confirmed=True)` を追加。**既にゴミ箱へ退避した1つのopaque IDだけ**対象、元の生ファイル名は引数に取らない。正確なSHA256と明示確認なしでは拒否。実行前にnofollow/regular/single-link/device/size/mtime/shaを照合し、既存運用ファイルを削除対象にしない。`scripts/gserver_files.py purge <restore_id> --expect-sha256 ... --confirm-permanent` に接続。保管領域を明示的に開放するための危険操作として、勝手な自動purge/スケジュール削除はしない。Commit `227a63100f978e3564a26f35f68eba9260b6f362`。
- **事故回帰テスト:** 追加3件は restore途中でfsync失敗→旧バックアップ保全、trashの元ファイルunlink失敗→原本維持、CLI purgeは確認必須/ハッシュ不一致拒否。`tests/test_storage_mutations.py` 10 tests + `tests/test_storage_cli_mutations.py` 3 tests、計**13/13 PASS（GPT隔離Linux環境）**。Commit `67b5f753efe71282b9d2e72cdc4b331e443feea2`。旧`test_storage.py`、旧`test_gserver_files.py` 及び実WSL G: E2Eは**この時点で未受領**。
- **GitHub読戻し:** `app/storage.py` 保護namespace、`app/storage_mutations.py` のatomically backed version/restore/purge、既存Owner CLIへの`hash/quota/trash/restore/replace/purge`接続と元の`put/get/list`維持、G:新規隔離フォルダーのHost安全E2Eテスト、13回帰テストのSource存在を確認。
- **Exact Next (非技術Masterは1ブロック実行):** `/mnt/g/Project/Gserver/repository` に`git pull --ff-only origin main`後、`python3 -m unittest discover -s tests -p 'test_storage*.py'`と旧 `test_gserver_files.py` の通過、通過後に`python3 scripts/verify_storage_mutations_host.py`でG:内**今回だけの新しい試験用ディレクトリ**で put→hash→replace→trash→restore→get→quota を実測する。本人の既存G:/F:ファイルを更新・削除しない。失敗時に無理に本番データで再試験しない。受入後にF04現行Dev KB/TGS連携や媒体断/復旧の残Taskへ移る。**F03/F01～F08全完成と誤記しない**。

## 2026-10-28 F03/GSR-S3-03 実装進行｜owner-onlyローカル更新・削除・復元・容量確認の実コードを追加

- **目的へ復帰:** Master「未完成のまま説明で止めず開発を継続」の最新指示に従い、妻PC/SMB/プロキシ/Firewallの検査・設定を対象外にしたまま、Gserver F03の未実装を直接進めた。今回**コード変更**であり、文書のみの作業ではない。
- **既存確認:** Docker/API 認証付き `/files` 一覧、`/download`、ホストCLI `put/get/list`、G:のREADME新規保存の過去実測PASS。今回の追加はデータ変更を伴うためWeb APIを安易に公開せず、OwnerだけがWSL terminalから使う `scripts/gserver_files.py` を拡張。
- **新Source:** `app/storage_mutations.py` に `quota`、SHA256 `digest`、`replace_version`（旧版が指定shaと一致した場合のみ一時書込み→旧版リンク保管→`os.replace`で原子的切替）、`to_trash`（SHA必須・削除前に旧版を保管）、`trash_list`（opaque IDとサイズ）、`trash_info`、`restore`（SHA必須・既存ファイル上書き拒否）を実装。CLIには `hash/quota/trash/trash-list/trash-info/restore/replace` と `put --max-bytes/--reserve-bytes` を接続。デフォルト空き容量留保64MiB、転送は1MiBストリームでメモリ節約。
- **隔離:** `app/storage.py` のpath component検証に `.gserver-*` hidden namespaceを追加し、`.gserver-trash`/書込み途中の `.gserver-part-*` を認証付き閲覧/取得APIからも遮断。Path traversal、symlink、硬リンク、想定SHA不一致、保存先容量不足をFail Closed。従来のAPI認証・Docker Compose・旧8765・G:/F:原本は変更しない。
- **テスト:** `tests/test_storage_mutations.py` 7件（復元・上書き拒否、alias/symlink/hardlink、容量、書込み失敗時の原本維持、旧版原子的変更、ハッシュ違い）、`tests/test_storage_cli_mutations.py` 2件（CLI全工程・quota/限度/重複拒否）を追加。GPT作業環境内の隔離したLinux一時フォルダーで**9/9 PASS**。これは**Windows/WSLのG: NTFS DrvFS実機でのE2E PASSではない**。当該PCにGitHub sourceを取り込んだ実機テストは未実施。
- **Host受入Source:** `scripts/verify_storage_mutations_host.py` はG:の既存files内に**一意の新しい小容量テストフォルダー**だけ作成、put→hash→replace→trash→restore→get→quotaを実行してSHA比較、試験用一時ディレクトリのみ自動片付け。既存README/動画原本/保護ACLを読込み変更せず、SMB/FWも触らない。模擬マウント上の受入テストはPASS、実G:は未実施。
- **GitHub証拠:** `9293f3443b360362f443147d9454853b7690dd0a`（保存エンジン）、`ba2733ca99e1689c1238fb888931e95351d25cff`（CLI）、`dffb3fdbb271727d8beec919ef4c84c9be894735`（9テスト）、`a2cb1aadee991c3879a25772b5202ce395f88893`（復元障害時の原本維持）、`2bc0bd4765118857a1c37858ee882234a0a9a11e`（Host安全実測）。実Hostでdocker build/最終受入はまだ行っていない。
- **Exact Next:** Master PC WSLの既存checkoutを`git pull --ff-only`、`python3 -m unittest discover -s tests -p test_storage_mutations.py` および `test_storage_cli_mutations.py` と旧 `test_storage.py`/`test_gserver_files.py` を実行、すべてPASSなら `python3 scripts/verify_storage_mutations_host.py` で**G:隔離新規テストのみ**実測。成功後はF03残ゲートの媒体切断/復元・容量逼迫・非同期誤終了への対処、F04 Dev KB/TGSの機能整合に連続接続。新しいWeb管理UIや妻PC/SMB等は作らない。

## 2026-10-28 Master最新判断｜妻PC利用・LAN/SMB共有の開発を中止し本来のGserverへ復帰

- **Master明示要件変更:** 「嫁はつかわないので、よけいなことをしなくてもいい」。妻PCからのファイル転送・共有は不要。以後、妻PCのWindows/ESU/ネットワーク検査、SMB3暗号化共有の有効化、妻専用資格情報、TCP445ファイアウォール変更、LAN共有のロールバック機構、ルーター/VPN/プロキシ追加は**現行開発スコープ外**。旧「Exact Next: 妻PCで検査」は**すべて失効**。再開はMasterからの新たな明示依頼がある場合のみ。
- **現物の保持:** Master Windows11の `G:\\GserverStorage\\files\\LAN-Inbox` は既にローカル作成済だが、SMB共有は未作成。作成済フォルダーを無断削除・改名・再権限変更しない。既存Docker/WSL Gserver、`127.0.0.1:18765`、旧8765、G:/F:原本、Windows Firewallとルーターの設定は保持。妻PCへ検査コマンドを要求しない。
- **本来の次の実装優先:** `docs/requirements/FINAL_ACCEPTANCE.md` のF01～F08を正本として、G:の認証付きローカル保存 F03 の未完成操作（更新/削除/容量・媒体切断保護）、Web/BotのCLI運用F02、G-ACE Dev KBのCurrent/検索/rollback F04、TGS連携・バックアップ/隔離復元 F05、F06～F08受入を完成させる。妻PC/SMBがF03の受入必須条件であるかのように扱わない。新しい作業・一括自動実行を勝手に開始しない。
- **証拠区分:** 既存LAN-InboxディレクトリとそのACLは実機PASS、Gserver Docker/API実行は既往PASS。ただしF03総合完了、外部SMB共有、妻PC E2Eはそれぞれ別であり、実施していない部分を完了扱いしない。

## 2026-10-28 妻PC検査の誤実行が判明｜Master Hostの実機検証として隔離・スクリプトをfail closed

- **Master報告の実測**: 2026-10-28 15:14頃、`windows_wife_lan_readonly.ps1` 新版をPowerShellで実行。Windows `POWERSHELL_PARSE=PASS`、`OS_FAMILY_BY_BUILD=WINDOWS_11_FAMILY`、25H2 / build26200.8894、`MASTER_GSERVER_MARKERS=BOTH_PRESENT`、`HOST_ROLE_HINT=LIKELY_MASTER_GSERVER`、仮想NIC候補2件を除くLAN IPv4候補1件、Private1/Public0、`VERIFY=PASS`。`MASTER_GSERVER_MARKERS=BOTH_PRESENT` により**検査元はGserver Master Hostの可能性が極めて高い**ため、妻Windows10の現況証拠として使用禁止。Masterの個別IPは公開Repoに記載しない。
- **ソース不具合を修正**: 妻PC用の検査をGserver Master自身で実行した際に従来 `VERIFY=PASS` を返し、妻PC確認済みと混同する恐れがあった。Master固有2 marker同時存在なら明示 `WIFE_PC_PROBE=REJECTED_MASTER_HOST` でfail closed/exit1 とする。妻PCで両markerのない場合は `WIFE_PC_PROBE=NOT_IDENTIFIED_AS_MASTER`、ただし**それだけで妻本人のPCと暗号的に認証された証拠にはならない**。`tests/test_windows_lan_probes_contract.py` に回帰assert追加。新スクリプトはSource実装のみで妻PC実行・PowerShell Parserは未検証。
- **次の実作業**: 妻PC本体の画面上PowerShellで固定GitHub版の検査を実行。失敗時は `WIFE_PC_PROBE` を読み、別端末ログを確認。妻端末がWindows10ならESU/OSパッチ状態をWindows設定UI/別証拠で確認し、未保護なら家庭内書込共有は延期。ネットワーク開放・SMBアカウント作成は引き続き未実行。Master Windows11 `G:\\GserverStorage\\files\\LAN-Inbox` ACL、localhost18765、G:/F:既存原本は維持。

## 2026-10-28 「妻Windows10」用probeの実行ログはWin11 25H2｜Host同一性は未確認

- **提供された実ログ:** PowerShellがGitHub固定commit `4b0f3a57790bd4a63fb4c4dfff92fcff7662b847` の `windows_wife_lan_readonly.ps1` を取得し `POWERSHELL_PARSE=PASS`、本体 `VERIFY=PASS`、`CHANGES=NONE`。`WINDOWS_PRODUCT=Windows 10 Pro` と `WINDOWS_RELEASE=25H2`、`WINDOWS_BUILD=26200.8894` は**矛盾**する。Microsoft公式Windows11リリース表で **OS build 26200 = Windows 11 25H2** と確定。レジストリProductName文字列はこの端末で実OS世代を正しく表していない。従って **このログは「Windows10端末がESUで安全」とは証明しない**。`ESU_ENROLLMENT/PATCH_ELIGIBILITY=NOT_VERIFIED` はそのまま。実行した端末自体を証明するIDなし。実行シェルの端末表示とWSLのような仮想NIC候補だけでMaster PC確定とも断定しない。
- **Network実ログ:** `LAN_IPV4_CANDIDATES=3`, private1/public0。うちRFC1918候補の1つは `192.168.0.x`、2つは `172.16-31.x`（仮想NIC候補）。アドレスは個人の実機情報のため公開GitHub台帳に正確な値を保存しない。サーバー側FirewallのRemoteAddressや妻PC本人IPとして自動採用しない。
- **更新注意:** Microsoft公式Windows11 25H2表には `26200.8894` が**2026-07-18**の更新であり、2026-10-26時点の `26200.9725` より古い。最新パッチ未適用の可能性があるため当該PCでもWindows Update適用状態を確認する。強制OSアップグレード/再起動はしない。妻PCが本当にWindows10なら、その端末のESU実加入/OS更新を別途確認する。
- **Source修正:** `scripts/windows_wife_lan_readonly.ps1` が旧来のREGISTRY ProductNameを実OS名として出すのをやめ、Build >=22000を `OS_FAMILY_BY_BUILD=WINDOWS_11_FAMILY` と表示しProductNameは明示 `REGISTRY_PRODUCT_NAME_LEGACY` に改名。既知Master Gserverの**ローカル2つのファイル/フォルダが両方存在**するかだけをread-only確認し、Hostの候補を `LIKELY_MASTER_GSERVER` / `UNIDENTIFIED` として出力。IPは仮想NIC候補を集計のみとして除外（他の宅内IPv4を保持）。`tests/test_windows_lan_probes_contract.py` に静的source回帰検査を追加。
- **受入判定:** 共有開始は未許可。妻PCの実体・実Win10/Win11・パッチ状態/同一LAN・IPが不明なうちはTCP445制限値を仮定しない。Main Windows11側LAN-Inbox ACLの前回実機PASS、Dockerlocalhost18765、G:/F:原本は継続維持。本人確認/過去ログ・閲覧対象を推測しない。

## 2026-10-28 LAN TCP445残余63件のPrivate条件実PC PASS｜妻PCの読取ゲートへ進行

- **Master PC実測:** Source `32eddee...` にfast-forward、`tests/test_windows_lan_probes_contract.py` Python `3/3 PASS`、Windows `Parser.ParseFile` `POWERSHELL_PARSE=PASS`、`scripts/windows_lan_firewall_readonly.ps1` `VERIFY=PASS`。全規則811。`EXPLICIT_TCP445_ALLOW_RULES=3` (Private 1、Privateかつnon-single-IP 1、nonPrivate 2、3件app/service restricted)。`GENERIC_ANYPORT_APP_SERVICE_RESTRICTED=37`。`GENERIC_ANYPORT_OTHER=63`、`GENERIC_ANYPORT_OTHER_PRIVATE=63`、`GENERIC_ANYPORT_OTHER_PRIVATE_NON_SINGLE_IP=63`、`GENERIC_ANYPORT_OTHER_PRIVATE_SINGLE_IP=0`、`GENERIC_ANYPORT_OTHER_NONPRIVATE=63`、unknown port scopes0。既存Firewall/SMB/NTFSへの変更なし。**これはrule条件の件数であり、SMB445への実到達・ルーターWAN開放が証明されたわけではない**。LocalAddress/Interface/InterfaceTypes/EdgeTraversal/サービス実効スコープは未確認。新しい限定Allow規則を足すだけでは妻PC限定と保証できない。**813件等と誤記しない、実測は811件**。
- **進め方:** 同じHostの広いルール件数調査を細切れで繰返さず、次は独立した妻PC側の現況確認と安全なSMB3暗号化共有の設計を進める。妻Win10の通常サポートは終了しているため、Windows build/22H2・Microsoft ESU加入・更新適用を実機で確認し、保護されていなければ**LANファイル共有開始は保留**。ソース `scripts/windows_wife_lan_readonly.ps1` を補強してアクティブPrivate/Public profile数とRFC1918 IPv4候補を読取るよう変更、commit `4b0f3a57790bd4a63fb4c4dfff92fcff7662b847`。ESUの加入/更新の本当の判定はUI等の別確認まで`NOT_VERIFIED`。妻PC側PC実測は**まだない**。
- **受入ライン:** Local LAN-Inbox作成と個別ACL保護はPASS。妻PCからのSMB3暗号化接続・相互認証・実際の動画転送・SHA・旧Gserver無影響/停止・元戻しは未着手。Existing Gserver localhost127.0.0.1:18765および旧8765、G:/F:の原本を保護。家庭内TCP445をWANから公開しない。既存firewallルール811件への一括Disable/Resetは禁止。
- **Exact Next:** 妻のWindows10端末PowerShellから、GitHubのimmutable commitに固定した `scripts/windows_wife_lan_readonly.ps1` を取得→Windows Parser.ParseFileをPASSさせてread-only実行。Windows release/build/Profile/RFC1918 IPv4候補を収集し、ESUと実パッチ適用は別証拠として確認。ネットワーク共有を今すぐ作らない。インターネットが使えない場合は手元へ手動転送して同scriptをオフライン実行。妻PC情報をGitHub公開Repoへコミットしない。

## 2026-10-28 LAN TCP445 Firewall残余63規則をPrivate/接続元で追加分類するSource

- Master実機ログは下段の実測（811・Explicit TCP445=3、全3件app/service restricted、GENERIC_ANYPORT_OTHER=63、GENERIC_ANYPORT_APP_SERVICE_RESTRICTED=37、POWERHSHELL_PARSE=PASS、変更なし）まで。3件の明示的TCP445許可と63件のgeneric候補は、すべて直ちにSMB到達を証明するものではない。任意portの広い規則を無視して「妻PCだけにFW新規Allowすれば確実に限定」とすることも不可。
- **次のSource差分** `scripts/windows_lan_firewall_readonly.ps1` を増分分類。既存のread-only COMルール検査で、アプリ・サービス非限定generic候補の `GENERIC_ANYPORT_OTHER_PRIVATE`、`GENERIC_ANYPORT_OTHER_PRIVATE_NON_SINGLE_IP`、`GENERIC_ANYPORT_OTHER_PRIVATE_SINGLE_IP`、`GENERIC_ANYPORT_OTHER_NONPRIVATE` を匿名件数で出力。ローカルインターフェース・LocalAddresses・実効Firewallは依然 `NOT_VERIFIED` とする。`tests/test_windows_lan_probes_contract.py` の静的安全契約も更新。Commit `9af719f75301061b31969edf6900651255d21a46`。GitHub差分/構文の単純な整合は確認したが**新コードのWindows Parserおよび実行は未確認**。
- 次のHost Gate: Master PC clean→git pull→対象unit→Windows `Parser.ParseFile`→成功時のみread-only Firewall実測。妻Windows10のESU/実IPv4、Router外部445、SMB暗号化とネットワーク共有は未検証。**ネットワーク共有もFirewall設定もまだ作成しない**。既存Gserver Docker・G:データ・LAN-Inbox ACL PASSは継続保持。

## 2026-10-28 Windows Firewall 445詳細分類実PC PASS｜広域実効アクセスは未検証

- **Master PC実測:** GitHub `ea07f03...` へfast-forward、`test_windows_lan_probes_contract.py` 3/3 PASS、Windows PowerShell `Parser.ParseFile` `POWERSHELL_PARSE=PASS`。読み取り専用 `scripts/windows_lan_firewall_readonly.ps1` で `FIREWALL_RULES_INSPECTED=811`, `EXPLICIT_TCP445_ALLOW_RULES=3`, `EXPLICIT_TCP445_PRIVATE_ALLOW_RULES=1`, `EXPLICIT_TCP445_PRIVATE_NON_SINGLE_IP_RULES=1`, `EXPLICIT_TCP445_NONPRIVATE_ALLOW_RULES=2`, `EXPLICIT_TCP445_APP_SERVICE_RESTRICTED=3`, `GENERIC_ANYPORT_APP_SERVICE_RESTRICTED=37`, `GENERIC_ANYPORT_OTHER=63`, `UNKNOWN_PORT_SCOPE_RULES=0`, `CHANGES=NONE`, `VERIFY=PASS`。`NOTE=COUNTS_ARE_RULES_NOT_PROOF_OF_SMB_REACHABILITY` の通り、到達性、WAN、wife限定はNOT_VERIFIED。
- **意味:** TCP445を**明示**するAllowは3件で全件ApplicationName/ServiceName指定あり。Private向け1件はsingle IP指定でない。Generic anyport（アプリ/サービス限定37件、限定のない63件）は具体的な端末、LocalAddress、RemoteAddress、profile、Interfaceの実効条件をまだ含めていないため、63件全てがTCP445通信を通すと断定してはいけない。逆に、**63件の広い可能性**を残したまま「新規妻PC専用Firewall ruleを追加すれば妻だけアクセス可能」と断定してもいけない。Windows Defender規則811件を無断で停止/変更しない。
- **ゲート:** 新LAN-Inboxフォルダーの独立ACLはPC実機PASS、SMB network shareは未作成。今後はGeneric 63件が現Privateで実質許可候補かを**集計だけで追加絞込**し、妻Windows10の実ビルド/ESU/LAN IPv4と、Router WAN445非転送を確認。安全を満たす共有・アカウント・Firewall・取り消しをセットで実装するまで、SMB共有は公開しない。Gserver Docker127.0.0.1:18765/既存G:保存とACLは変更しない。

## 2026-10-28 Firewall 445監査実測PASS｜103件はSMB直接許可と同義でないためSource分類修正

- **Master PC実機:** `git pull --ff-only` で `9ee6f4d...` fast-forward、Python `test_windows_lan_probes_contract.py` **3/3 PASS**、Windows `System.Management.Automation.Language.Parser.ParseFile` **POWERSHELL_PARSE=PASS**。既存 `scripts/windows_lan_firewall_readonly.ps1` は `WINDOWS_FIREWALL_COM` → `FIREWALL_RULES_INSPECTED=811`、`ACTIVE_INBOUND_TCP445_ALLOW_RULES=103`、`BROAD_SCOPE_PRIVATE_TCP445_ALLOW_RULES=84`、`NONPRIVATE_TCP445_ALLOW_RULES=97`、`UNREADABLE_ALLOW_RULE_PORT_SCOPES=0`、`CHANGES=NONE`、`VERIFY=PASS`。**監査ツールの実行は成功したが、Firewall経由のSMB到達性自体はNOT_VERIFIED**。LAN-Inbox/既存Docker/README/G:原本への変更はない。
- **重要な集計誤解の修正:** 103/84/97件はコードがポート未指定(`*`)・全プロトコル許可を含め、アプリ/Windowsサービスの対象制限（`ApplicationName`/`ServiceName`）を区別しない数値。**「TCP445を使ったSMBが103件許可」「危険設定84件」「WAN公開97件」と扱ってはいけない**。Windows COM `INetFwRule` 仕様では個別ruleに ApplicationName, ServiceName, LocalPorts, Protocol, Profiles, RemoteAddresses条件あり。MicrosoftのSMB防御推奨も実効アクセスとルーター公開の別検証を要請。決して既存811件のルールを一括停止しない。
- **GitHub実装:** `scripts/windows_lan_firewall_readonly.ps1` を局所的に継ぎ足さず**完成ソース全置換**して、TCP445がportとして明示されたAllow(`EXPLICIT_TCP445_*`)と、一般の任意ポート系(`GENERIC_ANYPORT_*`)を分離。後者はアプリ/サービス限定か否かも区別。明示445許可についてPrivate/非Private、単一IPv4か否かを匿名件数で示し、実効通信やWAN公開を推測しない。`tests/test_windows_lan_probes_contract.py` には各分類の存在、破損source(二重フッタ/未閉regex)の再発防止を更新。Source commits `1b16bcf569975a61bced16bc00911f6f0430dc20`、`a96b05872bbfd3bead5b79057c44c305c4e36ad9`。**新scriptのWindows Parser/実機は未検証**。
- **Exact Next:** Master PC clean→`git pull --ff-only`→unit3件→**PowerShell Parser.ParseFile errors 0**→新分類read-onlyファイアウォール監査。確定結果を使い既存汎用ルールへ影響せず、妻PCだけを受け入れるshare/firewallルールとrollbackを検討。妻Windows 10 ESU・実IP・Router WAN445は未確認のため`New-SmbShare`/FW変更を勝手に実行しない。

## 2026-10-28 Firewall監査ScriptのPowerShell ParserError｜破損source全体の置換と再発防止

- **Master PC実測:** `git pull --ff-only origin main` で `83e1abe...` へ更新。Python `tests/test_windows_lan_probes_contract.py` = **2/2 PASS**。その後 `powershell.exe ... windows_lan_firewall_readonly.ps1` がWindows PowerShell構文解析時に `ParserError`。55行目 `Unexpected token FIREWALL_RULES_INSPECTED`、100行目 `string missing terminator`、閉じ `}` 不足等。**監査コードは実行されず**、Firewall/SMB共有/ACLの設定変更は発生しない。DockerとG:実保存、LAN-Inbox作成の実機PASSは維持。
- **GitHubの破損Source直接検査:** `scripts/windows_lan_firewall_readonly.ps1` は `$singleIPv4 = $scope -match ...` の正規表現途中で行が途切れ、`if (-not $ok)...` の後に余計な `if (-not $singleIPv4)` 以下の末尾コードが重複付加されていた。先のSource編集で文字列置換に `$'` を含むパターンをそのまま使用した際の特殊置換解釈が原因候補で、**本質は不正なSourceをAST検証せず送った実装・検証漏れ**。
- **修正:** Sourceを継ぎはぎせず1つの完成PowerShellとして再生成し、各 `GACE_RESULT` marker 1回、回帰test `tests/test_windows_lan_probes_contract.py` に正規表現閉じ/重複脚部/単一ヘッダ・フッタ検出を追加。Code changes `bce467d59ec51b542b18568ec9285f073526aeda` / `107e80c71a905f8cf75e40cc8580da03ee97c0a4`。GitHub readbackでは1つの完成sourceであり、**Windows実AST parseおよび監査動作は未実行**。Host COM auditは既存Firewall許可ルールのread-only bounded列挙に限る。
- **Exact Next:** GitHub pull後、修正したunit（3 test想定）→実Windows PowerShell `System.Management.Automation.Language.Parser.ParseFile` で **Parse errors 0** を必須条件にし、その時だけread-only Firewall監査を実行。ParserErrorなら本体を動かさずsource差分だけ修正し、何度も手元のWindowsネットワークやDocker環境を変更しない。Firewall 445の許可範囲が特定できるまではwife PCの未確認IPに対する共有を開かない。

## 2026-10-28 LAN-Inbox作成・ACL隔離実PC PASS｜次の2PC間ネットワークゲート

- **Master PC実測:** GitHub `8ae85ac...` fast-forward、`tests/test_windows_lan_inbox_contract.py` Python **2/2 PASS**。Windows `scripts/windows_lan_inbox.ps1 -Prepare` で `SAFE_PARENT`→`TARGET_COLLISION`→`CREATE_EMPTY_INBOX`→`SET_CHILD_ACL`→`READBACK`、`INBOX_STATE=CREATED`、`INBOX_INHERITANCE_PROTECTED=True`、`INBOX_BROAD_ALLOW_COUNT=0`、`G_PARENT_ACL_CHANGED=False`、`SHARE_CREATED=False`、`FIREWALL_CHANGED=False`、`VERIFY=PASS`。**`G:\\GserverStorage\\files\\LAN-Inbox` は実機作成・ACL個別保護PASS**。Dockerの認証付き一覧への反映、妻PCからの転送、復元はこれだけでは未実証。
- **次の理由:** TCP445に新しいwife-PC専用Firewall Allowを足しても、既存Firewallの広域SMB-Allowルールが生きていれば実効アクセス制限にならない。既存許可を無断変更しないため、COM経由で許可ルールをbounded・非機密情報だけ読み取る `scripts/windows_lan_firewall_readonly.ps1` を実装。Protocol ANY/不明なRemoteAddressesは保守的に対象。妻Windows10側は `scripts/windows_wife_lan_readonly.ps1` でWindows build/UBRとNICのRFC1918 IPv4候補を収集し、**ESU加入と実パッチ保護はNOT_VERIFIED**として扱う。両source用の `tests/test_windows_lan_probes_contract.py` も追加。Source commit `7be59dd775974591d33c6cbedf26f43f24d21f3d`、Firewall scope判定修正 `fc6f0e2c930b400bb958c98cfd7f8c50cc391a83`。**Master PC実行/妻PC実行は未受領**。
- **設計Gate:** 専用非管理者account・GserverTransfer共有 `EncryptData=True`・認証/NTFS ACE・妻PCの確認済みIPv4だけにTCP445を限定し、ほかの既存共有への影響/元に戻す手順を確保してからネットワーク共有を有効化する。SMB1有効化、Guest/匿名、Everyone広範Write、WAN445公開は禁止。妻PC Win10 ESU/更新とRouterのWAN公開はまだ不明。Windows10からSMB3暗号化が実接続できるか実測が必要。
- **Exact Next:** Master PCはGit clean→fast-forward→`python3 -m unittest discover -s tests -p test_windows_lan_probes_contract.py -q`→`scripts/windows_lan_firewall_readonly.ps1` の**読取のみ**。その結果から既存Firewall broad allowと個別share制限の整合を確認。妻PCでのread-only OS/IP probeは後続の別Host操作。繰返しDocker/README/ACLinbox作成試験は不要。

## 2026-10-28 G: ACL詳細実測｜親からの広範権限継承、受信専用LAN-Inbox設計・コード

- **Master Hostの確定実測:** `git pull --ff-only` で `bfce2d1...`、`scripts/windows_lan_acl_detail_readonly.ps1` 結果 `VERIFY=PASS`, `G_FILESYSTEM=NTFS`。親 `G:\\GserverStorage` と子 `G:\\GserverStorage\\files` は `*_INHERITANCE_PROTECTED=False` であり、各2件 `Authenticated Users` の広いALLOW ACEが**どちらも `INHERITED=True`**。`Modify, Synchronize` と `-536805376`（整数表示）で、`*_UNRESOLVED_ACE_COUNT=0`。4つの独立した権限ミスではなく、G:側の共通継承が両パスで見えている。権限の実効積は `SHARE_AND_NTFS_EFFECTIVE_ACCESS=NOT_VERIFIED`、`LAN_SHARE=NOT_CREATED_BY_THIS_CHECK`。**既存NTFS ACLは変更していない。**
- **判断:** 家庭内LAN用に既存 `G:\\GserverStorage\\files` 全体を共有するとREADME.md等の既存資産まで転送用アカウントに見せることになる。親G:継承ACLを削除すればWSL/Dockerや他用途を壊すおそれがある。**新規専用 `G:\\GserverStorage\\files\\LAN-Inbox` のみ受信対象**とし、同ディレクトリの継承を個別に保護する。親/ファイル原本のACLや他フォルダーを変更しない。ただし親に広い `Modify` があるため、親側からの削除権限なども含め完全な隔離/秘密保護が成立したとは判定しない。LAN接続自体にはさらにshare ACL・資格情報・Firewallのwife PC限定・SMB暗号化が必須。
- **Source実装:** `scripts/windows_lan_inbox.ps1` の `-Prepare` はG:実NTFS・親パス非reparse・ターゲット未存在を前提に**新規ディレクトリのみ作成**し、ディレクトリ単位で継承を保護し、SYSTEM/Administrators/実行OwnerのSIDのみにフル権限を設定してreadback。既存ターゲットがある場合は**変更せずVERIFY=FAIL**。不具合時も自動削除しない（データ損失回避）。`-Prepare`なしはread-only検査。Sourceの権限変更を検査する軽量 `tests/test_windows_lan_inbox_contract.py` を追加。初版 `ca5e260e79cfc29781145c0877cf7bcf73f14576`、既存ターゲットをfail closed＆.NET typed ctorへの修正 `c98cb6ae86078a4a3fafe046fe87bd65e18e38b1`。**Master PCでのunit/PowerShell構文/フォルダー実機作成は未実施。**
- **安全境界:** ScriptはSMB共有・アカウント・Firewall・ルーターを**変更しない**。既存 Gserver Runtime localhost18765、G:へのREADME実保存、F: KB原本を維持。妻PCのWindows10 ESU/更新とLAN address、Router WAN445非公開、Windows SMB1有効状態は未実証。**共有作成へ移る前に妻PC/Hostの証拠が必要**。
- **Exact Next:** PC clean→`git pull --ff-only`→対象Static contract test→ `windows_lan_inbox.ps1 -Prepare` で新規専用フォルダーのみ作成・ACL readback。成功後に既存Docker read-only treeで新LAN-Inboxが見えるか確認し、妻Windows10のセキュリティ状態とFirewall/SMB共有限定を確認。ソースやE2E未検証を完了としない。

## 2026-10-28 Windows11 SMB security audit実機結果｜監査PASS・安全共有は未許可

- **Master実測:** `git pull --ff-only origin main` で `f6f42a8` へ更新。初回セキュリティread-onlyで `VERIFY=PASS` だが内訳は `SMB1_OPTIONAL_FEATURE_STATE=NOT_VERIFIED`, `SMB_SIGNING_REQUIRED_REGISTRY=0`, `SMB_SIGNING_EFFECTIVE=NOT_VERIFIED`, `SMB_SHARE_ENCRYPTION_EFFECTIVE=NOT_VERIFIED`, `BROAD_WRITE_ACE_COUNT=2`, `ACL_UNRESOLVED_IDENTITY_COUNT=0`, `FIREWALL_445_REMOTE_SCOPE=NOT_VERIFIED`, `ROUTER_WAN_445_FORWARD=NOT_VERIFIED`, `WIFE_PC_SECURITY_PATCH_STATUS=NOT_VERIFIED`, `CHANGES=NONE`, `SMB_SHARE_CREATION=NOT_PERFORMED`。**検査成功≠安全共有の設定合格**。署名必須値0は既存Windows SMB serverで強制されないことを示すが、暗号化接続なら完全性保護を含み、署名欄だけで安全判定しない。Windows11ホストの署名を全共有に強制する変更は既存デバイス接続に影響しうるため無断でしない。
- **リスク分類:** broad Write 2件は広いSIDグループに対するフォルダーACL許可の候補。まだ親から継承か、Everyone/Auth Users/Usersのどれか、Share ACLとの実効積、外部からの可視性は不明。標的G:フォルダーのACLを無断に変更しない。
- **次のSource:** `scripts/windows_lan_acl_detail_readonly.ps1` を追加（commit `6516012d800cdbd0a00d020d44eeff96fb18c6a9`）。`G:\\GserverStorage` 親と `G:\\GserverStorage\\files` の広範書込グループ種別・権限・継承有無とG: filesystemだけ、個人名/秘密を出さずに読む。公式Microsoft SMB仕様に沿う設計補足は `docs/architecture/LAN_SMB_SECURITY.md` 更新済。**PC新probe未受領**。残ゲート: SMB1実状態/妻Windows10 ESUと実際のSMB dialect、暗号化/認証、Firewall wife-PC only、router WAN445非公開。
- **次:** 新ReadOnly ACL詳細ゲート→G: subtreeだけの非破壊ACL計画・専用アカウントと共有権限/取消手順の実装。WAN/Firewall未確認では共有を公開しない。旧Gserver localhost18765、旧8765、F:原本は維持。

## 2026-10-28 Master判断：家庭用回線のSMB共有はセキュリティゲート先行

- **Windows 11 Host直近実測PASS:** MasterがSource `423bb40...` に更新し `scripts/windows_lan_preflight.ps1` 実行。`TARGET_DIRECTORY=YES`, `SMB_SERVER_SERVICE=Running`, `PRIVATE_PROFILES=1`, `PUBLIC_PROFILES=0`, `GSERVER_SHARE_NAME_IN_USE=False`, `SMB_445_LISTENING=True`, `CHANGES=NONE`, `VERIFY=PASS`。これは**共有可能条件の一部**でありFirewall許可・WAN遮断・SMB dialect/暗号化/署名・妻PCの保護状態のPASSではない。`SMB1_REGISTRY_VALUE=REGISTRY_UNSET` / `SMB2_REGISTRY_VALUE=REGISTRY_UNSET` は実有効状態不明。LAN_FILE_TRANSFER=NOT_ENABLED_BY_THIS_CHECK。
- **ユーザーのセキュリティ要請:** 家庭用回線だからと無保護で共有を始めず、プロキシ必要性と安全な通信プロトコルを事前評価する。家庭内2PC間の動画転送では一般的なHTTPプロキシは不要。Windows SMB2/3 + 共有単位の暗号化(`EncryptData`) + SMB signing + 専用非管理者アカウント + share/NTFS両ACL + Windows Defender Firewallの妻PC限定TCP445受信 + ルーターからWAN445への転送禁止 + WLAN WPA2-AES/WPA3を先行要件とした。SMB1/Guest/Everyone無制限/ルーター445公開は禁止。リモート利用が必要になったときだけ専用WireGuard系VPNを別途検討。
- **Windows 10リスク:** 妻Windows10の一般サポートは2025-10-14終了。ただしMicrosoftの2026-10-28時点の公式説明ではConsumer ESU登録により2027-10-12まで保護可能な対象あり。妻PCのEdition/ESU/Windows Update/実IPは未観測。安全性を推測して書込み接続を許可しない。
- **GitHub追加:** [`docs/architecture/LAN_SMB_SECURITY.md`](architecture/LAN_SMB_SECURITY.md) に脅威モデル・許可順・撤去/ロールバック・受入を記載。`scripts/windows_lan_security_readonly.ps1` を追加し、Master PCで未確認のSMB1機能状態、SMB signing registry、対象G: ACLのEveryone/Authenticated Users/Users broad write ACEを**匿名化したカウントで読取**。TCP445 firewallの遠隔許可範囲、Router WAN公開、妻PC更新状態は **NOT_VERIFIED** と明示し、結果がPASSでも**shareを作成しない**。実Host実行は未受領。Source commit `3bb54a1d23f023077c2c34217e4c5c55f27a1b43`。
- **Exact Next:** このsecurity read-only scriptの実機結果のみ取得。危険なSMB1/広範Write ACEが出れば既存リソースを壊さず対象共有側で制限できるか先に設計。妻PC Windows10更新状態と最終IP範囲を確認してから新規専用資格情報・暗号化共有・スコープ限定Firewallを実行。既存Docker GserverとG: readback PASSに戻る反復は不要。

## 2026-10-28 Windows LAN事前検査：SHARE_NAME RemoteException修正

- **実PC:** 2026-10-28 Master Windows11。GitHub `4b3bdaf...` まで fast-forward後、`WINDOWS_LAN_SMB_LIGHTWEIGHT_PREFLIGHT` 実行。`TARGET_DIRECTORY=YES`、`SMB_SERVER_SERVICE=Running`、`SMB1_REGISTRY_VALUE=REGISTRY_UNSET`、`SMB2_REGISTRY_VALUE=REGISTRY_UNSET`（**実際のSMB1/2有効無効とは同義ではない**）、`PRIVATE_PROFILES=1`、`PUBLIC_PROFILES=0`。その後 `PHASE=SHARE_NAME`→`FAILED_PHASE=SHARE_NAME`→`ERROR_TYPE=RemoteException`→`CHANGES=NONE`→`VERIFY=FAIL`。TCP 445未到達、共有名の衝突有無は不明、LAN転送未開始。Gserver Docker/G:保存の既存PASSはそのまま。
- **原因候補/修正:** Sourceで共有名の存在確認に `net.exe share GserverTransfer 2>$null` を使用。PowerShell停止優先 `$ErrorActionPreference='Stop'` では「共有が存在しない」場合のnative stderr処理が `RemoteException` を出すため誤停止し得る。Windows環境固有の詳細がないため根本を断定しない。**コマンドを取り除き**、HKLM `SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Shares` 内の単一名称 `GserverTransfer` の値存在を.NETの読取専用APIで判定。キー自体が読めなければ `UNKNOWN` を表示し、誤って「空き」と言わない。共有名の取得以外のフェーズ・設定は変更しない。Commit `c67f622bbb0b88d7ceeb2d2906fb300d86ac6278`。
- **Exact Next:** Master PCのSourceをfast-forwardし `scripts/windows_lan_preflight.ps1` のReadOnly再実行（大規模再テスト、Docker再build不要）。TCP445と共有名readback後、実共有・NTFS ACL・認証・Firewallを対象Host最小権限で実装。以前のG: dedicated folderのみ対象、SMB1/Guest/Everyone無制限・WAN公開は禁止。Dev KB/TGS進捗は独立で継続。

## 2026-10-28 Windows LAN事前検査：OutOfMemoryException→軽量段階式へ修正

- **PC実測:** MasterがPowerShellでGitHub `4f3e026...` へfast-forward後、`scripts/windows_lan_preflight.ps1` 初回実行。結果 `PROJECT=Gserver`、`ACTION=WINDOWS_LAN_SMB_READ_ONLY_PREFLIGHT`、`ERROR_TYPE=OutOfMemoryException`、`CHANGES=NONE`、`VERIFY=FAIL`。初期版は単一try内で `Get-SmbServerConfiguration`・`Get-NetConnectionProfile`・**無制限の `Get-SmbShare` 全列挙**・`Get-NetTCPConnection` を実行し、失敗段階を出していなかったため、**どの操作でメモリ例外になったかは未確定**。Windows自体の物理RAM不足と断定しない。Gserver Docker/Volume・G:実ファイル保存は前回PASSのままであり、LAN共有を作成した証拠はない。
- **Source改修:** `scripts/windows_lan_preflight.ps1` をcommit `ed918f02c61fe52598060997de1ae2b5d0b064d4` で軽量化。フル共有一覧と重いSMB CIM設定取得を廃止し、対象G:ディレクトリ存在/reparse、`LanmanServer` Service、SMB1/2レジストリ値（未設定なら `REGISTRY_UNSET` として推測しない）、接続プロファイル、固定共有名の競合を `net.exe share GserverTransfer` で調べる方式、.NETのローカル TCP445 listener に置換。各フェーズ前に `PHASE=...`、失敗時 `FAILED_PHASE=...` と例外クラスだけ表示し、ホスト固有IP・資格情報は出さない。全て読取専用、LAN共有作成/Firewall変更なし。
- **Exact Next:** 実PCで最新Sourceへfast-forwardし同スクリプトを再度1回だけ実行。PASSなら実観測したService/Profile/445/共有名の条件に基づきSMB共有とNTFS ACLの最小化設計に進む。FAILなら `FAILED_PHASE` の箇所だけ調査・修正し、全体テスト/再ビルドはしない。WindowsのPublic→Private、SMB1、ゲスト、Everyone書込の勝手な有効化をしない。実転送/家族PC読戻し・Dev KB/TGSは未検証。

## 2026-10-28 家庭内動画転送：Windows標準SMBを再利用・読み取り専用事前検査Source

- **新しい実行物:** `scripts/windows_lan_preflight.ps1` をコミット `5ad80bd2fa407b50d3795c79eba5c22d1824de5c` でGitHubへ追加。Master Windows 11 Host側で `G:\\GserverStorage\\files` の実ディレクトリとreparse拒否、SMB Serverサービス、SMB1/SMB2設定、アクティブなPrivate/Publicネットワークプロファイル、共有名衝突・既存対象共有・TCP445 Listen状態を**読み取り専用**で検査。原則GACE_RESULT包みで結果返却し、設定/パスワード/個別ローカルIP/他shareの実名を記録しない。Host実行は未受領。
- **設計判断:** 妻Windows 10から同じ家庭内Wi-Fi経由で4TB級動画を送る実用経路は、不要なGserver HTTP書込みAPI/Web管理UIを追加するよりWindows標準**SMB2/3の認証付き共有**で `G:\\GserverStorage\\files` のサブツリーだけを対象にする。既存Gserver HTTPは `127.0.0.1:18765` のまま。SMB1や匿名/ゲスト/Everyone無制限を有効化しない。**共有を作る/Firewallを変更する/ネットワークPublic→Privateを変更する操作はまだ実施していない**。その前に本人ホストの実設定とLAN到達の境界・専用Principal・NTFS ACL・無断公開の危険・復元経路を検討。
- **Exact Next:** Master PCで `git pull --ff-only` 後に `powershell.exe -NoProfile -ExecutionPolicy Bypass -File G:\\Project\\Gserver\\repository\\scripts\\windows_lan_preflight.ps1` を実行して readback。実行結果で安全な既存条件を判断し、最小ACL・認証付きLAN共有・元に戻す機能へ進む。未検証共有を作成済みと報告しない。
 
## 2026-10-28 G:実ファイルコピー初成功｜保存・SHA256照合・認証付きAPI読戻しPASS

- **Master PC実測**: WSL Ubuntuで `git pull --ff-only` により `ebd4ce3...` へfast-forward。最新 `app/storage.py` のcontextmanager修正を含む `python3 -m unittest discover -s tests -p test_gserver_files.py -q` = **5/5 PASS**、`python3 -m unittest discover -s tests -p test_storage.py -q` = **9/9 PASS**。Host CLI `python3 scripts/gserver_files.py put README.md` が `{"bytes":6226,"name":"README.md","sha256":"171b13dcef1bfd851eb88a3dd1090ff0a9a119e54850bab3cf58e90795a0bdeb"}` を返し、`cmp -s README.md /mnt/g/GserverStorage/files/README.md` 成功。CLI `list` = `README.md` file size 6226。sudo認証後のDocker `gserverctl.py storage-list` で認証付きAPIから同一実ファイルを読戻し。**`GSERVER_FILE_COPY=PASS`**。
- **受入判定:** 単一ローカルファイルの `put`→G:指定子フォルダーへの**非上書き実書込み**→bytes/SHA256→OS同一比較→Dockerで認証済みAPI一覧、実PCでPASS。既存 `GserverStorage/files` の他ファイルやF:の原本は触らず、旧8765サービス/現18765ポート維持。再buildや新規有料AI/定期タスク不要。
- **未完:** `get` の実G:読戻しをローカル別ディレクトリへ行った証拠はまだない。奥さんのWindows 10端末からLAN転送・共有ユーザー権限・Windowsファイアウォール/Privateネット判定・SMB認証・大容量動画の断続再開/速度/空き容量/クォータ・Windows再起動後自動復旧、Dev KB・TGS・バックアップ/復号隔離復元は**NOT_VERIFIED**。F01–F08全体完成とはしない。
- **NEXT:** MasterのWindows 11・妻Windows 10の既存LAN環境をread-onlyで検査し、G:の単一許可フォルダーのみ**認証付き**SMB共有で転送できるよう安全な承認・ロールバック操作を設計する。Gserver 18765 HTTPは今まで通りPC内loopback限定、外部公開しない。SMB1/ゲスト共有/無制限Everyone書込/Firewall全開/家庭内ルータのポート転送は行わない。大容量転送はまずWindows標準SMBを再利用し、サーバー固有の独自HTTPアップローダーを重複実装しない。独立して実装できるDev KB/TGS連携にも継続着手。

## 2026-10-28 S3ファイル転送｜PC unit error 3件を診断し共有Storage例外境界を修正

- **実PC観測:** Masterの `git pull --ff-only` によりHost checkoutが `3c3aaa2...` へfast-forward。`python3 -m unittest discover -s tests -p test_gserver_files.py -q` が `Ran 5 tests` 中 `3 errors`。ケース `test_existing_symlink_and_out_of_scope_paths_rejected`、`test_failed_partial_write_leaves_no_published_file`、`test_round_trip_hash_and_no_overwrite` で本来 `FileExistsError/OSError` を報告する場所に `storage.StorageUnavailable` が発生。そのため `&&` により `put README.md` とG:実書込・CLI list・Docker storage-listは**一切実行されていない**。既存Docker/Volume/API read-onlyの前回PASSを否定しない。
- **根本原因:** `app/storage.py` の `@contextmanager Storage.directory()` と `open_file()` が `yield` を `try ... except OSError` 内に入れていたため、呼出し元のファイル重複拒否や書込ディスク満杯まで mount失敗 `StorageUnavailable` に誤変換する構造バグ。単にtestの期待値を変更して隠さず、**directory/fileのopen+fstat段階のOSErrorのみStorageUnavailableへ変換し、yield後の利用者操作エラーはそのまま伝播**するよう実コードを修正。既存のpath traversal/リンク/mount拒否、close確保は維持。さらに `tests/test_storage.py` で `yield` 内でFileExistsErrorとENOSPCを発生させて伝播を確認する新unit追加。**Source commit `8be1c0e6730adc5e27815a1f56e4256b689ac1a9`**。
- **現状と次:** GitHub Source修正は完了しPCの新test/実G:ファイル書込みは**未検証**。次は clean checkout→`git pull --ff-only`→**S3転送5 test+Storage unit**のみを実行してから、既存 `README.md` を新規保存（同名存在ならfail-closed）→CLI `list`→認証付きDocker `storage-list`、結果照合。旧Docker imageは変えないので再buildしない。既存G:原本/旧8765/LAN/KB/TGSは未変更。

## 2026-10-28 G:専用Docker readback実機PASS・Host CLIファイル転送Source追加

- **Master PC実機:** Windows PowerShell → WSL `/mnt/g/Project/Gserver/repository` `git pull --ff-only` で `13fff7a...` へ進め、Python `33 tests in 17.054s OK`、`sudo -v`、`python3 scripts/gserverctl.py enable-storage`（既存専用Docker container `gace-gserver-gserver-1` healthy）、`python3 scripts/gserverctl.py storage-list` → `{"entries":[],"next":null}`、`status` → `127.0.0.1:18765->8765/tcp`、末尾 `GSERVER_STORAGE_READ=PASS`。**Windows G:の専用子フォルダーがDockerに読み取り専用接続され、認証済みAPIから一覧を取得できた。** データ未登録のため空一覧は正常。元のG:全体やF:原本への接続ではない。
- **Source進捗:** 今回は既存GserverのDocker image/Volume/認証/Host 18765はそのまま維持。非破壊のHost WSL CLI `scripts/gserver_files.py` を追加。操作 `put LOCAL_FILE` は実G: mount確認・既存Storageの許可subtree/パス検証・symlink拒否・1MiBチャンクのstream copy・SHA256・fsync・ハードリンクで原子的な**新規保存のみ**・既存ファイルを上書きしない・部分ファイルの通常エラー時削除。`get NAME DIRECTORY` は保存側も新規作成のみ。`list` は既存StorageのAPIと同じ境界を使用する。コードはG:の **`GserverStorage/files` のみ**に保存し、他フォルダー、Docker volume、F:の原本は変更しない。Unit `tests/test_gserver_files.py` にreadback/重複拒否/禁止path/mount切断/途中disk full時のcleanupを追加。
- **証拠区別:** Source commit `c5777a3e0fdf1c00a5fdcafcb74062096b04bf36`。**Host CLI転送の新unit/実G:転送はまだ未検証**であり、既存の `GSERVER_STORAGE_READ=PASS` を新CLIのPASSに転用しない。Gserver自身のHTTPはまだ読み取り専用であり、別PCからのLAN送信・書込みHTTPアップロード・resume・削除/更新/クォータ/暗号化backup/KB/TGSは未完成。4TB大容量転送の速度・中断回復は未測定。
- **Exact Next:** 新CLI unitだけを実PCで実行し、G:\\専用ディレクトリへ小さな既存README.mdを1ファイル実保存して、`gserverctl storage-list` で認証付き実読戻し。新image再ビルド不要。これを確認後、より実用的なファイル送受信・Windows内/家内LANからのアクセス・Dev KB/TGS・隔離復元へ継続。定期Codex/別AI・追加管理UIは不要。

## 2026-10-28 S3 storage test blocker｜稼働中18765ポート競合のテスト誤判定を修正

- **PC実測:** `git pull` で `49c5b11...` へfast-forward後、`python3 -m unittest discover -s tests -p test_runtime.py -q` を実行。`32 tests` のうち `test_local_enable_disable_reuses_image_and_volume`、`test_local_failure_recovers_original_profile`、`test_switch_to_loopback_recreates_container_with_volume_preserved` が `OSError: [Errno 98] Address already in use`（`127.0.0.1:18765`）で失敗。**Gserverは既に18765番で稼働しているので正常な競合**。テストが実host socketをbindする欠陥で、Master/本番Gserver/ストレージ障害ではない。`sudo -v`以降は `&&` 連結で未実行なのでG: storage未接続のまま。既存serviceを止めたり、ポートを変えたりしてテストを通してはいけない。
- **GitHub Source修正:** `tests/test_runtime.py` の該当3ケースで `ctl.socket.socket` のport probeだけをmockし、**実稼働18765へ依存しない**よう変更。反対に、port conflict時は実Dockerへ一切触れず拒否することを確認する独立unitを追加。Commit `1c889e7ecc29f02cd850aa58ad30440c8bf1d3a3`。GitHubで変更後コードを読戻し確認。**PC unit再実行/Storage API実機成功はこれから**。
- **Exact Next:** PC clean Git→`git pull --ff-only`→対象unit（33件想定）→sudo→`gserverctl.py enable-storage`→`storage-list`→`status`。稼働中127.0.0.1:18765公開/既存Volume/image/旧serviceの保持を尊重。成功後にG:実ファイル送受信・Dev KB・TGS・隔離復元の未完成条件へ進む。失敗時は今回と違う箇所だけ修正し、重複した隔離smoke/再ビルドはしない。

## 2026-10-28 実PCローカルHTTP成功・G:専用読み取り接続を実装

- **Host実測PASS:** MasterのWSL Ubuntu checkoutがGitHub `8090474...` までfast-forward。Python unit `28/28 PASS`、`sudo` PASS、`gserverctl.py enable-local` → Docker network `gace-gserver_gserver-local-v2` Created → Container `gace-gserver-gserver-1` Healthy。`docker port ... 8765/tcp` が **`127.0.0.1:18765`**、`curl http://127.0.0.1:18765/health` が **`{"status":"ok","service":"gserver"}`**。Compose `status` は `127.0.0.1:18765->8765/tcp`、末尾 **`GSERVER_LOCAL=PASS`**。PC Runtime接続ゲート合格。**Windows側のlocalhost到達/Windows再起動後自動再開はまだNOT_VERIFIED**。旧プロトタイプの8765・G:原本・TGS未変更。
- **S3 GitHub実装（実機未検証）:** 既存イメージの `/files` `/download` 読み取りAPIを再利用し、`gserverctl.py enable-storage` / `disable-storage` / `storage-list` のCLIを追加。**固定専用 `G:\\GserverStorage\\files`**（WSL `/mnt/g/GserverStorage/files`）だけ作成し、Dockerへ親 `/mnt/g/GserverStorage` を `/mnt/g` として**read-only bind mount**、他のG:フォルダー/F:の原本を渡さない。WSL `/mnt/g` のmount証拠無しならfail closed、シンボリックリンク/別deviceは拒否。API bearer tokenは既存Docker永続volume内に非root0600権限でランダム生成して保持、公開GitHub/ログに出さない。compose snapshot別SHA・release ledgerのstorageフラグを維持、停止/再起動/rollbackは同じ永続Volumeを再利用。元imageの再ビルド不要。**本番動作・実ドライブのPermission/readbackは未受領**。
- **受入境界:** 読み取り専用の専用フォルダー実利用を先に完成。アップロード/更新/削除・別PCからの転送・Dev KB/TGS・暗号backup/restore・Windows再起動後の持続起動は未実装/未実証。F01～F08を完了扱いしない。不要Web管理UIや重複CI/重い検証は増やさない。
- **最短Exact Next:** MasterのPowerShell→WSLから clean check・`git pull --ff-only`・対象unitだけ・`sudo -v`・`gserverctl.py enable-storage`・`storage-list`・`status` を1回実行し、実G:マウントとDocker側認可APIのreadback。必要に応じてWindows PowerShellから `http://127.0.0.1:18765/health` 到達も確認。失敗時は対象原因に絞って修正。次は実ファイル送受信・既存Dev KB・TGS・復元を優先。

## 2026-10-28 ローカルHTTPポート公開失敗→原因特定・修正反映（PC再確認待ち）

- **実機失敗:** Masterが `git pull --ff-only` で `6690bfe...` に更新後、`tests/test_runtime.py` Python **26 PASS**、`sudo` PASS、`python3 scripts/gserverctl.py enable-local` で `Network gace-gserver_gserver-local Created`、Container `Healthy` を確認。しかし `curl http://127.0.0.1:18765/health` は `curl: (7) Failed to connect`。再実行しても status の PORTS は **`8765/tcp`だけ**でホスト公開無し。**GSERVER_LOCAL=PASSは出ていない。** Docker service本体は保持中。原因を「ユーザーがポートを閉じた」と扱わない。
- **原因:** Docker Engine 29系 + Compose 5系の `internal: true` bridge 単独接続では、host-local publish要求が無視される報告（moby/moby discussion #53256）と完全一致。既存Controllerは`access=loopback`をledgerへ保存しても新実体へのnetwork/port反映を検証せず、2回目の`enable-local`で`ps`だけを返すため自己回復できなかった。
- **修正Source:** `scripts/gserverctl.py` のloopback用snapshotを **新Manifest `*.loopback-v2.json`** で作成。新たに `gserver-local-v2` **通常bridge** に接続（従来の内部のみのネットワーク設定との衝突回避）、Host公開は**`127.0.0.1:18765:8765`固定のみ**。これはContainer outbound制限を旧`internal: true`と同一にはしないため、外向き通信防止が別途要件ならHost FWで検証する。局所公開とは区別する。image/Volume/old immutable snapshotsは削除しない。profile変更時`docker compose up -d --force-recreate --wait`を使い、失敗時旧版への強制再作成rollback。既にledger `access=loopback` のときも `enable-local` により再適用できる。回帰Unit **2件追加**、既存unitのnetwork期待更新。Commit **`8b7235164905558b7e30968f997b67b116780bd1`**。Source実装済み、**新修正のPC unittest/Runtimeは未受領**。
- **Exact Next:** Master WSL `/mnt/g/Project/Gserver/repository`のclean state確認→`git pull --ff-only origin main`→変更のPython unittestのみ→`sudo -v`→`gserverctl.py enable-local`→`docker port ... 8765/tcp`でHost publishの実測→WSL `curl --fail http://127.0.0.1:18765/health`→Windows→WSL localhost forwarding確認。**同じ旧失敗コマンドをそのまま再実行させない**。合格後にG:マウント/本人の認可パスに進み、既存KB/TGS接続/復元を続ける。CI/本番G:/KB/TGSはNOT_VERIFIEDのまま。
 
## 2026-10-28 ローカル専用HTTP接続｜Source実装済、PC動作確認待ち

- CHATが既存 `scripts/gserverctl.py` に `enable-local` / `disable-local` を追加。固定の **`127.0.0.1:18765:8765`** だけを公開するバージョン別SHA256固定Compose snapshot (`*.loopback.json`) を作成し、Docker networkは `internal: true`、既存Volume/image/release ledgerを維持する。ポートが埋まっていたら変更前に拒否。既存の8765/Python試作や他サービスを止めない。`start|stop|status|logs|rollback|recover` は選択中のlocal/isolated構成を再利用。`disable-local` で元の隔離構成へ戻す。**GitHub Source commit `16ca27d3ec7d053219e9ecb30fcdef389265a973`、回帰Unit 4件追加。PC実行・テストは未受領。**
- **即実機NEXT:** Master既存WSL checkoutで `git pull --ff-only origin main` → `python3 -m unittest discover -s tests -p test_runtime.py -q` の対象変更回帰テスト → `sudo -v` → `python3 scripts/gserverctl.py enable-local` → `curl -fsS http://127.0.0.1:18765/health` → `status`。変更/依存が不一致ならfail closedして原因箇所を修正する。以前PASSの隔離Runtime試験再実施・image再ビルド・Volume削除・Windows C:再調査は行わない。HTTP `/health` は非公開環境での通信経路確認に限り、G:/KB/TGSが使える証拠ではない。
- この後、必要に応じてMasterから最小限の `/mnt/g` 実mount/readbackを取得し、認可対象subtree/秘密の安全なローカル注入だけを最小構成で仕上げる。公開RepoにHost秘密/実データを書かない。Windows reboot証拠未受領。

## 2026-10-28 S2正式Dockerコンテナ起動 PASS｜次はローカル接続・G:マウント

- **Master PC実測:** Windows PowerShell `wsl.exe -d Ubuntu -u gace -e bash -lc ...` から、検証済みアプリ/Compose/Controllerに差分がないことを確認し、`sudo docker --host unix:///var/run/docker.sock build --quiet --network=none` → `python3 scripts/gserverctl.py activate` → `status` を実行。`GSERVER_ACTIVATION=PASS`。専用Volume `gace-gserver_state` **Created**、専用Container `gace-gserver-gserver-1` **Up (healthy)**、image `sha256:3216607d7a54dd3daec5e6e88318e921f296b1ef650039f4195dc5c7122b7880`。**試験用ではなく実運用Controller管理下で起動中**。旧原本や他Service、G:の実データを触っていない。
- **重要:** base Composeは `network_mode:none` + published port無し + G:/F: bind無し + auth credential未注入。現時点の `healthy` は**内側で/healthが200**のみ。通常ユーザーがWindows/WSLからHTTP接続できる、ファイルが使える、Dev KB/TGSが使えるという意味ではない。管理用CLI `scripts/gserverctl.py status|logs|stop|start` は本稼働Projectを対象にして使える。永続Volumeを消す `docker compose down -v` 等は厳禁。
- **直近完了条件:** (1)既存host listening ports 8765と別port(例18765)の空き状況、および `/mnt/g` の実mount状態を最小限read-onlyで確認。(2)前段の固定immutable imageとrelease ledger/rollbackを壊さず**127.0.0.1限定HTTP公開**と管理者本人が指定したG:サブツリーへの最小権限bindを追加。(3)host HTTPヘルス/認証/Storage readback、既存service退行無し、Docker CLI restart/rollbackを実機確認。必要な秘密・実データパスは公開Repoに登録しない。(4)既存Dev KB・TGS・Backup/Restoreへ進める。**同じ隔離テストや同一Docker buildは繰り返さず**、管理UIを新規開発しない。Codexを自動起動・委任しない。
- **注意:** Windows Host再起動後のWSL+Docker自動起動、実G:接続、外部TGS・KBは今なお未検証。F01–F08完成とは扱わない。

## 2026-10-28 Gserver S2隔離実機検証 PASS｜初めて実コンテナ起動を実証

- **証拠:** Masterから Windows PowerShell → `wsl.exe -d Ubuntu -u gace` で一括実機試験 `bash scripts/verify_pc_runtime.sh` の完全な出力を受領。試験時PC source `SOURCE_SHA=6db18616b81fc158a553ee455c38cca15358c2a6`。**Python unittest 60/60 PASS、UI挙動4/4 PASS**、旧原本SHA固定stagingは実Docker container Healthy / internal `STAGING_HTTP=200` / host ports NONE。新packaged imageは実Docker build成功、専用隔離Container Healthy、再作成・stop/startのhealth、Volume内sentinel永続化PASS。
- **実Controller:** 違うimage IDへの更新→元image IDへrollback→stop/start→同じVolume sentinel維持を実Dockerで確認。`CONTROLLER_SMOKE=PASS;IMAGE_UPDATE_ROLLBACK=PASS;PERSISTENCE=PASS;HOST_PORTS=NONE`。結果 `SUBCHECK_VERIFY=PASS;RUNTIME_SMOKE=IMAGE_RECREATE_PERSISTENCE_OFFLINE`、`LOCAL_VERIFICATION_RECEIPT=SAVED`、最後に `VERIFY=PASS;SCOPE=ISOLATED_SOURCE_AND_PACKAGED_RUNTIME;F01_F08=NOT_COMPLETE`。試験専用コンテナ/Volumeはcleanupで削除、既存Host service回帰ガード含む。認証の問題は今回解消。
- **SHA整合:** 検証時 `6db18616b81fc158a553ee455c38cca15358c2a6` からGithub最新main `bdf16abcc10866e7d4088605f0a12b0f5ff63a7e` までの差分は `AGENTS.md`、`docs/CURRENT.md`、`docs/requirements/FINAL_ACCEPTANCE.md` の**文書3ファイルだけ**。実行コード差分なし。そのため上記Runtime証拠は隔離Runtimeの現ソースに適用可能。ただし新機能/本番への証拠流用は不可。
- **受入範囲:** GSR-S2-02の隔離Docker build/起動/volume永続化とGSR-S2-05の実コントローラー更新・旧版差戻し（同じアプリのfixture）は実機PASSへ昇格。完全なS2本番配置（ユーザー手元からアクセス可能なloopback listener/必要なcredentialと最低限のG: subtreeのみ承認済みでmount/WSL起動連動）やS3ストレージ実体・F04 KB/F05 TGS/F05 Backup&Restore/F08 E2Eは**未実装/未検証**。テスト用環境は終了しており、通常利用Gserver本体が常時起動したとは宣言しない。CIは未実行。
- **最短Exact Next:** staging/隔離smokeを再度求めない。**VS Code/Cursor CLI-first**で利用するGserver本体の**ローカル限定**配置を、既存ポート/サービス/設定/セキュリティ競合を非破壊で照合したうえで実装・有効化して、実利用者の `start/status/logs/stop/rollback` を実機で検証する。既存HTML管理画面の拡張・Codex自動定期タスクは不要。その後、G:上の明示許可subtreeへの安全なStorage接続・読み書き、既存Dev KB実接続、TGS/暗号backupと隔離restore、WSL再起動/失敗復旧へ進む。検証受領後も同じテストを反復して進捗にしない。

## 2026-10-28 Windows/WSL実機ディスク監査｜前回の+37GB判断を撤回

- **最優先の訂正:** PowerShell `Win32_LogicalDisk`実機readback: C:総容量 **117.86 GiB**、使用 **82.47 GiB**、空き **35.38 GiB**。D:総容量 **465.66 GiB**、使用 **48.98 GiB**、空き **416.68 GiB**。Masterの「整理後C:使用量約80GB」と同じ単位で比較した概算差は**約+2.47GiB**。CHATが「117GB使用し、約37GB増」と記録したのは**総容量を使用量と混同した誤り**で、ここに明確に撤回する。元80GBの測定時点/丸め/単位は未確認のため、増加原因や厳密な差分はこれ以上断定しない。
- WSL distro登録の実物: `Ubuntu`, `\\?\D:\WSL\Ubuntu\ext4.vhdx`、**10.13GiB**。D:へのWSL移設は既にできている。Ubuntu内のDocker `DockerRoot=/var/lib/docker`、`docker system df`: Images **193.9MB**、Build Cache **191.3MB**、Containers **0**、Volumes **0**。`df -h /`: WSL rootの使用約**8.0GiB**。**Dockerの大量データがC:を約37GB消費したという仮説は否定**。ただし物理C:の全ファイル増減の時系列証拠はない。
- 観測したC:内候補サイズ（占有容量であり、最近の増加分ではない）: `hiberfil.sys` **7.95GiB**、Windows Update download **4.06GiB**、VS Code roaming **2.46GiB**、VS Code extensions **1.63GiB**、Codex `.codex` **1.12GiB**、User Temp **0.83GiB**、Cursor Roaming **0.25GiB**、Docker Local **0.04GiB**。重要データ/既存開発の作業状態を含みうるので推測で削除しない。
- **NEXT:** Codexへの「+37GB緊急原因調査」依頼は誤認識に基づくため取り下げる。追加の重い再帰調査、Docker再インストール、WSL移設、強制キャッシュ削除は不要。C:空き35.38GiBを維持し、大容量化が実測されたときのみ対象限定の確認を行う。Codexは本来のGserver S2〜S7機能実装に集中し、本人専用CLI運用と既存データ保護を厳守。

## 2026-10-28 Master修正｜単独CLI運用・C/D配置/容量優先

- 最新のMaster意思は **単独使用でVS Code/Cursor操作のみ**。管理者Web画面は必要なし。既存UIは除去のために工数を掛けないが、これ以上管理UI機能を盛らず、CLI/Composeで起動/停止/ログ/復旧を完結させる。必要なWeb/APIは維持。F01～F08の完成条件は[FINAL_ACCEPTANCE.md](requirements/FINAL_ACCEPTANCE.md)で修正。
- **PCの確定既往:** C SSD約118GiB(前回空き約34～35GB、Master最新申告空き36GB)、D HDD内 `D:\WSL\Ubuntu`にWSL ext4.vhdx既存配置済み（当時約6.67GiB）。WSLとDockerを勝手に再配置しない。Docker Engine29.9.2はWSL内。docker/containerdの使用先、Linux mountと実Windowsディスク・image容量の2026-10-28時点readbackは **NOT_VERIFIED**。
- D: HDD上のWSL ext4領域と`/mnt/d`/`/mnt/g`のcross-filesystem I/O性能差を現物で評価し、既存親Project Git/Worktree境界を崩さず必要最小の配置最適化を行う。Docker cache/build imageの不要増加を抑制。実データ削除・Docker prune・rootdir移設・WSL VHDX移設は別途検証/権限条件まで禁止。
- **Exact Next (Codex):** ディスク容量については直上のWindows/WSL実機監査済み（C:使用82.47GiB／空き35.38GiB、WSL VHDXはD:）。重複した容量調査をせず、S2 CLI・実機runtimeの受入 → G: Storage・正式Dev KB・TGS・隔離復元の未実装を減らす。管理UI拡張や新規重い依存は避ける。Codexは時間指定自律ジョブ/別AIの起動禁止。

## 2026-10-28 Codex継続｜S2差戻し修正・S3読取実装

- Owner=Codex。再開HEAD `28281a6b516f7059df65ce1ce8ae933076a1d34a`、検証プロセスなしを確認して変更再開。旧HEADの結果が後から届いた場合は、そのHEADの証拠として扱い、新しい実装のPASSへ転用しない。
- **S2 Source:** sudoでimage環境変数が失われる経路を修正。image別のCompose snapshotをローカルへ原子的保存/hash検査し、後日のソース変更から起動/差戻しを分離。Docker接続はPCのUnix socketへ固定。実controllerの更新/差戻し/volume保持を検証する隔離smokeを一括試験へ追加。
- **S3 Source:** 明示許可されたmount配下の一覧/ページ分割/ストリームdownload/Range、traversal・symlink・hardlink・特殊ファイル・Windows alias拒否を実装。UIのフォルダー移動/保存/再試行/ログアウト取消、応答と安全な監査ログのrequest IDを追加。`GSERVER_FILES_ROOT`未設定では無効、実G:/F:への接続・変更なし。[S3契約](architecture/STORAGE_S3.md)。アップロード/更新/削除は未実装。
- **検証:** Python 60件、既存Windows Nodeを利用したUI挙動4件、snapshot Compose config、bash構文を検証。Dockerをmockした試験・mountを模擬した合成ファイル試験を含み、実機コンテナ/実USB/browser E2Eではない。正確な終了結果は本変更のIssue #9記録に記載。
- **証拠継続:** `verify_pc_runtime.sh`がローカルstateの`gserver/verification/latest.json`へHEAD/phase/exit/timestampだけを保存する。生ログ/秘密なし、ソース変更時PASS禁止。同じ検証を再依頼する前にreceiptを読む。
- **PC Runtime:** 元ソースSHA不変。sudo認証は引き続き本人端末が必要で、更新版Docker起動/永続性/実rollback未確認。実行結果未受領をPASSとしない。新しい検証の重複要求はしていない。
- **CI/TGS/Backup-Restore:** 未実行/未実証。S4既存KB・S5接続権限/暗号backup・S6監視・S7再起動/復元を完了扱いしない。F01–F08と46タスクを維持。
- **Exact Next:** 最新HEADの一括検証receipt/結果を照合→失敗箇所だけ修正・必要範囲再検証→S2正式配置/ingress/Windows持続稼働。安全に独立可能なS3以降の実装は継続。原本/秘密/公開設定/Contabo/既存サービスには変更なし。

## 2026-10-27 Codex実測・S2ソース実装（現セッション）

- **Owner / Tasks:** Codex、GSR-S1-04/S2-01/S2-02/S2-05の実装差分。開始時main `8e2dcaa19da67f04feb5f9ea2608d62d8bcbe497`。F01–F08 / 46タスクは未完了のまま。旧記録は履歴として保持する。
- **Source:** 既存試作SHA一致を確認し、原本を変更せず`app/gserver.py`へ取り込み。stdlibを再利用し、ローテーションログ、認証必須状態API、未mount時503、状態確認UI、接続数/timeout上限を追加。digest固定Dockerfile、永続volumeのCompose、image ID固定の起動/停止/更新/差戻し、更新中断journal/recover、隔離再作成・ログ永続性smokeを実装。[S2実装契約](architecture/RUNTIME_S2.md)。公開port・実データmount・秘密の作成はなし。
- **Local tests:** WSL上の全41 Python unittest PASS（既存staging10件を含む）。bash構文とCompose config PASS。HTTPテストは一時loopbackサーバーと合成認証fixture、ライフサイクルはDocker境界mock。隔離smokeの既存volume拒否・起動失敗時ログ/cleanup・cleanup失敗伝播もfake Dockerで4件検証。コンテナ起動の証拠ではない。
- **PC Runtime:** WSL/Compose v5.6.1、元ソースSHA一致、既存4サービスactive、旧8765待受なし。staging実行は`SUDO_ACCESS_FAILED`/exit16で停止、Docker socketへの非sudoアクセスも拒否。コンテナ起動・ログ永続性・image rollback・再起動後稼働は **NOT_VERIFIED**。管理者認証を迂回せず、既存サービスへの操作なし。
- **CI:** この変更のCIはNOT_RUN。新Workflowは作成していない。
- **TGS / KB:** 正式Repoの既存契約を読取照合。KBのMVS/単一Currentを再利用し、TGS ZERO/vNextを区別する。Gserverの接続権限・受領先・実送受信は未確認。新Reader/新検索基盤/Project ID流用/既存秘密コピーなし。
- **Backup/Restore:** NOT_IMPLEMENTED / NOT_VERIFIED。永続volumeの再作成試験はバックアップ復元証明と扱わない。
- **Rollback:** 元PCソース/設定/データ/サービスは無変更。新ソースは導入前。controllerは前imageへ差戻し、途中中断はjournalから`recover`、volume削除なし。ただし実Dockerで未実証。
- **Exact Next:** Master端末で`bash scripts/verify_pc_runtime.sh`を実行（staging→packaged runtimeを一括検証）し、既存sudo認証で固定image/永続log/recreate/offline検証→実ログに基づく修正→認証/ingress/drive境界の承認済み設定による正式配置。続いてS3認可ファイル操作、S4既存KB、S5既存TGS+暗号backup/隔離restore、S6/S7監視・Windows再起動・全E2E。本人操作依頼済み、非同期ジョブは予約していない。

以下は前回までの履歴。

> **最新2026-10-27 23:00 JST：MasterがGserver開発を既存VS Code (WSL Ubuntu) Codexへ単発委任。** 完全な現況、未完了の隔離起動10テスト、本体/S3～S7/正式Dev KB/TGS完成条件、保護範囲は [Codex引継ぎ](CODEX_HANDOFF_2026-10-27.md) と [Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9) の冒頭を正本とする。**Docker Engine/Compose host基盤は実機PASS、Gserver本体の最新staging修正版はPC未実行**。旧見出しにある「Docker未導入」は10/23時点の履歴であり現況ではない。バックグラウンドCodex/自動レビュー/追加AI起動は許可されていない。

**判定：DESIGN_MIGRATED / PC_TRIAL_SOURCE_VERIFIED / FULL_RUNTIME_NOT_VERIFIED**

## 開発目的
手元PCのC:/D:/F:/G:を適切に役割分担し、**Windows最小Host→WSL UbuntuのDocker/Composeコンテナ主体**でWeb/API/Storage/既存Dev KB/TGSクライアント等を独立運用するGserverを完成させる。Contaboの既存Docker/Composeサーバーと共通の運用契約を保ち、追加Serverへ拡張しやすい疑似クラウド基盤とする（各Hostの実体・権限は分離）。

## 現在位置
- NotionのF01～F08完成条件とS0～S7全46タスクをGitHub文書へ移行。
- PC本体のソースコード・実サービス構成・Codex実行確認は未取込。以前のlocalhost health 200は過去の限定報告。2026-10-22の旧PC調査では既知候補でGserver名のディレクトリを確認できず、旧起動報告との配置差がある（現在のPC実測やソース不存在の証拠ではない）。
- 既存KB正本：[seigo-gace/gace-dev-kb](https://github.com/seigo-gace/gace-dev-kb)／MVS／ModuleCatalog Current。旧kb-systemは別資産。
- TGSは既存サーバーを利用する構想。Gserver→TGS実送受信・復元は未確認。
- OSSセキュリティ/監視は既存機能と不足を突き合わせ、必要最小限を採用。
- GitHub Project #1のItem登録：**NOT_VERIFIED**（このRepo/Issues作成で自動登録されたとみなさない）。
- Repoは現在Public。実機の非公開資料やSecretsを保存しない。

## 追加確定要件（2026-10-23）

Master決定：GitHubは開発管理のみに使用し、GserverのWeb/Bot/Storage/既存KB等の**通常運用はGitHub接続なしで成立**させる。Git由来の開発履歴はSource provenanceとして保持し、更新/受領とローカル通常検索を分離する。TGSは別Hostへの独立した通信依存。完成後にはRepoをPrivate化するが、今はPublicであり機密を登録しない。

受入詳細は requirements/FINAL_ACCEPTANCE.md の横断必須条件で統一。設計変更以外のPC Source/Runtime・GitHub非依存実証・Private化はNOT_VERIFIED。PC Codex/限定Server AI投入はMasterのみが判断する。

## Master確定：Dockerコンテナ主体／疑似クラウドの複数Host共通運用（2026-10-23）

- Docker Engine + Docker ComposeをGserver正式運用の主経路とし、Contabo等と**サービス定義・起動/更新/rollback・監視・秘密/volume・リソース管理を共通化**。ホストごとのWindows/WSL・パス/USB・公開/認証は差分管理。Kubernetes等の大規模管理基盤や新Token/Workflow/サーバーAIを勝手に追加しない。
- PCの`docker=NOT_FOUND`（WSL PATHの実測）は`DOCKER_RUNTIME=NOT_INSTALLED_OR_NOT_ON_PATH`であり、「Docker廃止」ではない。Podmanの存在をDocker主経路の代替決定としない。**Docker導入・Compose実起動・二Host共通運用の実機受入は未実施**。
- aaPanelは採用確定ではない。Master既定は不要/未使用であり、実機activeのため依存を最小確認してから安全に扱う。109行HTTP試作はコンテナ化完了ではない。
- 先ほどMaster実機で`/mnt/g/Project/_TelegramGroup`へのシンボリックリンク5件が全て`LINK_OK=True`、`VERIFY=PASS`。**元の5資産移動/サービス変更なし**、再利用・統廃合は別作業。正式Dev KBは`seigo-gace/gace-dev-kb`、旧kb-systemは除外。
- NEXTはS2-01 Docker/Composeの責務・配置・既存サービスとの非破壊移行単位の確定→S2-02の必要Runtime導入/実機Compose試験。F01-F08は元の番号/46タスクを維持。GitHub切断で通常運用可能なことはF08で検証。


## 2026-10-27 現状復元・整合監査（PC再実測待ち）

- **Authority:** server-core manifest SHA `fcd38e3` / GPT CHAT Rule #17、Gserver [Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9) の現在位置を2026-10-27に読み直した。GitHub Project #1へのCurrent item登録は **NOT_VERIFIED** のまま。
- **Source/Repo:** 監査開始時のGserver `main=199786cbc3212b030a4e53c49dd39dfe1f66803e`（最終更新10/23）。当時のtreeは19ファイル（docs/requirements/tasks、AGENTS、README、scripts/pc_gserver_inventory.py、tests/test_pc_gserver_inventory.py等）で、**Gserver実アプリ、Dockerfile、compose.yaml、Docker Engine導入済み証拠はRepo内にない**。PR #10/#11はmerged、GitHub Actions runs合計0。8 Stage・46タスクは受入完了を宣言できず、Stage Issuesは未完了のまま。
- **PC歴史証拠:** 10/23にWindows F:と `F:\\G-ACE-KB` 既存ディレクトリの存在を確認、`/mnt/g` mounted・Gserver 109行HTTP試作/ソースSHA一致/8765 HTTP200を当時実測、Telegram5リンク `_TelegramGroup` 全5件PASS、Podman 4.9.3/socket active、Docker engine/Compose未導入を実測。旧 `kb-system` はMasterにより放棄済みで再利用対象外。正式Dev KBは [gace-dev-kb](https://github.com/seigo-gace/gace-dev-kb) の正本、F:は原本保護。
- **2026-10-27の変化:** VS Code WSLとContabo SSHの接続回復およびCodex拡張旧版 `26.1007.21434` のインストール・接続復旧はMasterから報告されたが、**Codexジョブ実行許可を意味しない**。当日Windows経由のWSL検査は`WSL=OK`/`GSERVER_FILES=OK`ながら`GSERVER_HTTP=000`（localhost試作が応答せず）。このため10/23のHTTP200を現在の稼働PASSとして引用しない。
- **未確認:** 10/23にDocker Engine/Composeのインストール一括コマンドを提示したが、**実行結果は届いていない**。現在のDocker/server/container、8765、G:/F:mount、site_total/Redis/aaPanel、Telegram5リンクは**PCの10/27限定Read-only再測定待ち**。PCソースをGitHubにImportした証拠なし。KB検索/MVS/ACTIVE/rollback、TGSログ/暗号backup/download/隔離restore、Web/UI/API/Storage実機E2E、GitHub切断E2Eは未完成/未検証。
- **NEXT:** 10/27のPCでDocker/Compose実在・既存サービス/マウントと試作APIだけを一度で確認し、該当するS2-01/S2-02の未達を埋める。再びBot統廃合や放棄KBを調査しない。Docker/Compose-first・増設Server共通運用・Contaboを別Hostとして保護する本来のF01～F08は維持する。無許可のCodex/ServerAI委任や定期タスクは行わない。

## 2026-10-27 Docker/Compose導入ユニット｜Source完了・PC実行待ち

- Master PC最新 readback（`ACTION=PC_S2_RESUME_RUNTIME_READONLY`）: `VERIFY=PASS`; Docker Engine/Compose CLI/packageなし、Podman4.9.3/socket active、Redis/site_total/btpanel active、G: mounted、F:はWSL未マウント、Telegram参照リンク5/5、Source SHA一致、試作8765は`URLError`。これによりS2-02のDocker導入が未完了と再確定。
- GitHub実装 [commit `56b3b87`](https://github.com/seigo-gace/G-ACEserver/commit/56b3b87a8f23b53bd0039ac936acd6452f637118): `scripts/install_wsl_docker_compose.sh` と `tests/test_docker_bootstrap_contract.py`。Ubuntu24.04/WSL/SHAの前提、Docker公式鍵fingerprint、既存APTパッケージ削除防止のsimulation、Docker/Compose導入、`network_mode:none`一時smoke、Podman/Redis/site_totalの事後状態確認を実コード化。**ローカルbash構文と静的契約7/7 PASS**だが実機導入とSmokeは **NOT_RUN**。
- Master PCへの導入は、このコミットに固定したSHAを検証する1回実行のWSLコマンドで行う。Docker group付与なし、Contabo/TGS/Telegram/旧kb-systemへの変更なし。新規Docker Engine daemonはホストNetwork/Firewallへ作用し得るため、ポート公開を行わず、既存稼働と分離。Podmanを自動で削除しない。
- **NEXT（作業継続）:** MasterのWSL実機導入読戻し→S2のDocker/Compose環境での既存Gserver sourceの互換化・非破壊コンテナ化→S3 Storage/Web、S4正式Dev KB、S5 TGS送受信+隔離復元、S6/S7運用・全受入の実装。インストール成功だけでF01～F08の完成とはしない。

## 2026-10-27 Docker host verified; isolated existing-source staging prepared

- **HOST VERIFIED:** Master PC (2026-10-27) `ACTION=WSL_DOCKER_COMPOSE_BOOTSTRAP` `VERIFY=PASS`, Docker daemon `29.9.2`, Compose `v5.6.1`, official signing fingerprint verified, apt install count 7/remove count 0, isolated `hello-world` Compose smoke PASS, no published ports. Podman socket, Redis and site_total remain active. This completes only **GSR-S2-02 runtime bootstrap/smoke**, not app containerization or Gserver F01–F08.
- **STAGING IMPLEMENTATION:** [commit `33c79ab`](https://github.com/seigo-gace/G-ACEserver/commit/33c79abc301488369edbc69b7bea2d6884cf6f4d) introduced `deploy/compose.gserver.staging.yaml`, `scripts/smoke_gserver_staging.sh`, `tests/test_gserver_staging_contract.py` (7 static checks; not claimed as executed CI). Does **not copy/modify** old Python source; bind-mounts only `/mnt/g/Project/Gserver/app/gserver.py` read-only with SHA256 guard. Isolated `network_mode:none`, no host port or access to G:/F: data, nonroot / all capabilities dropped, limited resources, healthcheck only localhost:8765; any old 8765 process untouched. Staging project is guarded against name reuse and shut down afterward.
- **STAGING HOST EVIDENCE:** `NOT_RUN` until Master executes pinned snapshot of compose+script on WSL. Image `python:3.12-slim-bookworm` is a mutable tag **only for one-off staging**; pin digest and build actual app runtime / data volumes after source dependencies are confirmed. Existing source may require root path/config; failure of isolated healthcheck means compatibility needs work, not that Gserver data is destroyed.
- **NEXT:** Run pinned read-only staging test on PC, inspect only the bounded failure evidence if no 200; adapt / package existing app without altering original; implement persistent Compose service, authorized G: data mounts, existing Dev KB, TGS ZIP/receipt/readback/isolated recovery, then S7 E2E. The entire Gserver Mission is still open.

## 2026-10-27 isolated staging FileHandler /logs runtime repair

- Master WSL reported `unittest 9/9 PASS` and isolated container `exited (1)`, with bounded pre-cleanup traceback locating the failure to existing `app/gserver.py:22` `logging.FileHandler(LOG_PATH)`: `FileNotFoundError: '/logs/gserver.log'`. Stage `STAGING_HEALTH_FAILED`, diagnostic readback succeeded, temporary container successfully removed. This is **a missing writable staging log directory**; do not label Docker Engine/Compose failed or the Gserver app production-ready.
- Source fix [commit `7b3538a`](https://github.com/seigo-gace/G-ACEserver/commit/7b3538a0317628a887108828a2ac15ee9ae2087b) mounts a **private ephemeral tmpfs** at `/logs` (UID/GID 65534, 0700, 16 MiB, noexec/nosuid/nodev), leaving host logs and G: data unaffected; staging adds assertion that the existing Python FileHandler created `/logs/gserver.log`. Test case added for private tmpfs, with log verification guard in [commit `b033a12`](https://github.com/seigo-gace/G-ACEserver/commit/b033a1293c3cf45bedf7749cf49b34e04adbccdf). New static source guard assertions 10/10 agree with saved scripts/configs, but **10 actual Python unittests and WSL staging smoke are NOT YET RUN**.
- **NEXT:** Execute pinned+blob-verified revision `b033a1293c3cf45bedf7749cf49b34e04adbccdf` on PC for 10 static tests + isolated runtime HTTP200 + ephemeral log file existence + teardown. On success, proceed to real Gserver service packaging, **persistent production logs/data volumes** and service health/restart/port design under S2; then S3 storage, S4 official Dev KB, S5 TGS, S6/S7 acceptance. Never retain staging tmpfs as production log storage.

## 次の実装単位
2026-10-23のWSL実機読戻しで旧Gserver試作（109行、SHA256=41e0df51db854fd562f748b4f8dbcc558d0052d2d52d2957f6d3a89b9f61e15c）のsource内容、localhost HTTP200、PID/port所有、既存Web/Redisの一部稼働を確認済み。Windows F:のG-ACE-KB関連既存フォルダも存在確認済み。**一方、正式Dev KB検索E2E、GserverのF01-F08全機能、TGS復元は未確認。** 旧kb-systemは放棄済みで再利用対象外。

**NEXT：GSR-S2-01** — 既存Gserver試作とWeb入口、Linux実行配置、F:/G:データの責務と非破壊移行・差戻しを確定し、S2-02以降の必要実装へつなぐ。Telegram関連5資産は一つの保留グループとして扱い、移動・再利用判断は別作業に切り分ける。**これをGserver開発の停止条件にしない。**

## 作業判断の権限
Master：最終目的／優先順位／不可逆影響／限定Server AI投入判断。
ChatGPT：既存ルール #17に従う計画/証拠の調整。
PC-Codex：既存ルール #16に従う指定タスクの最小実行。
GitHub現行Issueが実行状態、Notionは会議・歴史の参照。実機/元RepoがSourceとRuntimeの一次証拠。

## 実装済みの誤認禁止
ドキュメントとタスク移行は実Web/Bot/KB/TGSのコード導入・Windowsでの稼働証明・外部公開・DR復旧の完了ではない。
タスク完了証拠：TASK_ID、対象OS/Repo、Source path/SHA、変更diff、依存/競合、test exit、PC Runtime、TGS readback、rollback、NEXTをIssueへ記録する。

## GitHub管理の実際の再開入口
- [CURRENT Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9)を新チャット/PC Codexの入口とする。
- Stage Issues [S0 #1](https://github.com/seigo-gace/G-ACEserver/issues/1)から[S7 #8](https://github.com/seigo-gace/G-ACEserver/issues/8)へ、46タスクをチェック項目として登録済み。
- GitHub Project #1へのProjects v2項目追加は未検証。Project登録済みと誤記禁止。
