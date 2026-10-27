# CURRENT｜G-ACEserver
## 2026-10-28 Master修正｜単独CLI運用・C/D配置/容量優先

- 最新のMaster意思は **単独使用でVS Code/Cursor操作のみ**。管理者Web画面は必要なし。既存UIは除去のために工数を掛けないが、これ以上管理UI機能を盛らず、CLI/Composeで起動/停止/ログ/復旧を完結させる。必要なWeb/APIは維持。F01～F08の完成条件は[FINAL_ACCEPTANCE.md](requirements/FINAL_ACCEPTANCE.md)で修正。
- **PCの確定既往:** C SSD約118GiB(前回空き約34～35GB、Master最新申告空き36GB)、D HDD内 `D:\WSL\Ubuntu`にWSL ext4.vhdx既存配置済み（当時約6.67GiB）。WSLとDockerを勝手に再配置しない。Docker Engine29.9.2はWSL内。docker/containerdの使用先、Linux mountと実Windowsディスク・image容量の2026-10-28時点readbackは **NOT_VERIFIED**。
- D: HDD上のWSL ext4領域と`/mnt/d`/`/mnt/g`のcross-filesystem I/O性能差を現物で評価し、既存親Project Git/Worktree境界を崩さず必要最小の配置最適化を行う。Docker cache/build imageの不要増加を抑制。実データ削除・Docker prune・rootdir移設・WSL VHDX移設は別途検証/権限条件まで禁止。
- **Exact Next (Codex):** 管理UI開発を止め、C/D空きと`/var/lib/docker`/`/var/lib/containerd`/WSL VHDXの保存先を読取計測 → 必要なS2 CLI・実機runtimeの受入 → G: Storage・正式Dev KB・TGS・隔離復元の未実装を削減。新規管理UI工数のために完成を遅らせない。Codexは時間指定自律ジョブ/別AIの起動禁止。

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
