# CURRENT｜G-ACEserver
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
