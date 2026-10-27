# Gserver → Codex 開発引継ぎ（2026-10-27 JST）

> **現行実行用の引継ぎ。** Masterがこの会話で、Gserver開発の実装・デバッグ・テスト・安全なローカル統合を、VS CodeのCodex（WSL Ubuntu）に一度まとめて委任した。これはCodexの**対話セッション内のGserver限定作業許可**であり、Codexタスクの定期自動実行、別Agent/Server AIの起動、PRの自動レビュー、課金を伴う常時ジョブ、別Hostの本番変更の許可ではない。

## 1. 正本と実行者ルール

- Repo: https://github.com/seigo-gace/G-ACEserver （**現在PUBLIC**）。
- Current / 実行位置: https://github.com/seigo-gace/G-ACEserver/issues/9 。**過去記録は時点付きであり、末尾の新しい実測が優先。** `docs/CURRENT.md`、`README.md`、`AGENTS.md`、`docs/requirements/FINAL_ACCEPTANCE.md`、該当 `docs/tasks/S0.md` ～ `S7.md` と `docs/architecture/` を必要分だけ読む。
- G-ACE Rule Plane manifest: https://github.com/G-ACE-inc/server-core/blob/main/operations/github-project-rule-plane.json → **CodexにはSERVER_AI Rule #16のみ**: https://github.com/G-ACE-inc/server-core/issues/16 。GPT CHAT用 Rule #17 をCodexにロードしない。コマンド作成・Hostへの指示は既存server-coreの `docs/COMMAND_ROUTINE.md` / `docs/MASTER_TERMINAL_COMMAND.md`。
- 本引継ぎ作成時のGitHub main HEAD: `314f597aad9e9287e65eb1c8795217b26de83cf9`。**着手時に最新HEADと他者変更を再読**し、古いSHAで上書きしない。GitHub Project #1 Item登録済みかは未検証。Issueの存在で登録済みとみなさない。

## 2. Mission（変更禁止）／完成の定義

Gserverは手元Windows 11 PC（WSL Ubuntu 24.04）を用いた、Docker Engine＋**Docker Compose** 主体の疑似クラウド基盤。Web/API/管理UI、個別Bot、G:の認可付きストレージ、正式G-ACE Dev KB（BM25/Vector/Hybrid/KG/MCP・単一Current・ModuleCatalog受領・rollback）、Contabo側の既存**TGS/TGserver**とのログ・検索・暗号化バックアップ／ダウンロード／隔離復元、監視と自動復旧を**非技術者一人で管理可能**にする。将来別HostへCompose定義・起動・監視・永続データ・rollbackの運用契約を再利用できるが、別Hostの実変更は別権限。通常運用はGitHubへの接続・Actions・OAuth無しで動くこと。

**最終受入:** `docs/requirements/FINAL_ACCEPTANCE.md` のF01～F08とS0～S7既存46タスクを原形のまま閉じる。実PC Web/UI/Storage/Bot/KB/TGSの代表E2E、エラー時のUI戻る・変更・復旧、再起動・USB切断・TGS障害時のfail-closed、有界spool、実ログ/バックアップ送受信とSHA/復号/隔離復元、GitHub通信遮断時の正常運用、Source/CI/Runtime/Backup証跡、旧版rollbackを**それぞれ確認**。単なるHTTP200/ユニットテスト/Compose稼働を「完成」と呼ばない。F08完了後のPublic→Private変更はMaster保護判断まで実施しない。

## 3. 最新実機（すべて2026-10-27 Master提供ログに基づく）

- 実行Host=**手元PCのWSL Ubuntu**、ユーザー `gace`、VS Code `WSL: Ubuntu` に接続済み。**Contabo SSH側とは別Host**。Codex拡張とアカウントは既存同期済みで復旧済み、追加のCodex CLI/extension/認証を作らない。
- 手元の**既存PC試作ソース**: `/mnt/g/Project/Gserver/app/gserver.py`、SHA256 `41e0df51db854fd562f748b4f8dbcc558d0052d2d52d2957f6d3a89b9f61e15c`（約109行）。設定 `/mnt/g/Project/Gserver/config/settings.json`、既存ログ/データは同Project内。**この現物フォルダ直下に.gitはない**（以前実測）。ソースをGitHubで勝手に同じものとみなさない。まず本体実体・依存・秘密の有無を読み取る。機密や実ログをPUBLIC Repoへ上げない。
- `/mnt/g` mounted、`/mnt/f` **不在**（Windows F:のKB原本が消えたという意味ではない）。F:既存原本 `F:\G-ACE-KB` は保護し、勝手に移動/初期化/再索引しない。正式Dev KB Repo=https://github.com/seigo-gace/gace-dev-kb 。**旧`kb-system`は放棄済みで対象外**。
- `/mnt/g/Project/_TelegramGroup` の閲覧用リンク5/5 PASS、元のTelegram Bot 5資産は移動していない。**採否/統廃合は別案件**。Gserver全体のBot運用要件は残すが、この5資産の統廃合を今回の先行作業にしない。
- 導入実測: Docker Engine **29.9.2**、Compose **v5.6.1**、公式APT鍵検証PASS、`hello-world`の隔離Compose実起動PASS、外部ポートなし、APT削除0。既存`podman.socket`、`redis-server`、`site_total` は active、`btpanel` も直前実測でactive。Docker groupを付与していないので必要なDocker操作は `sudo` を使う。sudoユーザーパスワード実値は収集しない。
- 古いホスト側 `127.0.0.1:8765/health` は10/27時点 `URLError`。過去10/23のHTTP200を今の稼働状態とみなさない。既存Pythonプロセス/aaPanel/Redis/site_total/Podmanを`kill`や`restart`で無断変更しない。
- RepoのDocker導入ソース `scripts/install_wsl_docker_compose.sh` はすでに実機PASS済み。**Dockerの再導入・OSセットアップを繰り返さない。**

## 4. 正確な再開点 — 既存Python試作の隔離Compose実行

- GitHub `scripts/smoke_gserver_staging.sh`、`deploy/compose.gserver.staging.yaml`、`tests/test_gserver_staging_contract.py` を現HEADから使用する。既存PCソースはSHA guard＋read-only bind。stagingは `network_mode:none`、外部ポート公開0、nonroot、read-only rootfs、limit、実データmountなし、試験後 `compose down`。
- 10/27 13:08 JSTの実機実行結果：**Python unittest 9/9 PASS**、Python image取得・コンテナ作成PASS、Gserverアプリが**exited(1)**、原因ログ `app/gserver.py:22` の `logging.FileHandler(LOG_PATH)` が `FileNotFoundError: '/logs/gserver.log'`、試験コンテナは削除済み。Docker daemon障害ではない。
- **修正済みで未再実行:** `/logs`をコンテナ**内だけ**のnonroot書込み可能tmpfs（16MiB/mode0700）にする修正を [`7b3538a`](https://github.com/seigo-gace/G-ACEserver/commit/7b3538a0317628a887108828a2ac15ee9ae2087b) で実装。[commit `b033a12`](https://github.com/seigo-gace/G-ACEserver/commit/b033a1293c3cf45bedf7749cf49b34e04adbccdf) でログファイル生成assert＋Python静的テスト**10件**に増加。正本 `main=314f597...` はこの修正を含むが、**最新10/10テストとステージHTTP200はPC上まだNOT_VERIFIED**。
- **最初に実施:** 最新checkoutとPCソース実体を安全に照合→ `bash -n`、既存10 unittestの実実行→ `sudo docker compose ... config` と隔離smoke→ `/health` HTTP200、`/logs/gserver.log`存在、host portなし、既存サービスの状態不変、cleanupを確認。失敗時はcleanup前の `STARTUP_DIAGNOSTICS_BEGIN..END` / bounded Compose logsから根因を特定、必要な修正/テストを**同じ作業内で継続**。過去の失敗ケースを目的のない反復にしない。実PC証拠なしにPASSを書かない。
- 既存PC本体ソースの必要なコンテナ適合を確認後、**試験用のtmpfsログを本番ログの永続保存と誤認しない**。Linux FS上の安全なコード/config、ホスト依存のmount、G:データ/ACL、ログ容量、secret、health/readiness、restart、version pin/rollback、利用者UIへの導線を実装。旧8765の所有者・port競合をread-only確認し、並行検証→安全な切替。勝手に既存Hostデータや起動サービスを潰さない。
- GitHubの実コードとPC現物の差分を確認し、**公開可能なソースだけ**既存Repo/親Project内の管理されたcheckout/branchへ統合する。PCの`.git`がない現物に`git init`や強制resetを無断で適用しない。新しい兄弟Project/Worktree/認証経路を作らない。CIが0件ならCIが走ったと称さず、利用可能なローカルテスト/実機readbackで確認する。

## 5. 隔離試験後の実装優先順

1. **S2 残:** 既存サービス調査からDocker/Compose本番配置、依存ロック・正本Dockerfile、Web入口/portと認証、ログ/永続volume、安全な起動停止/healthと非技術者向け管理UI、Windows/WSL再起動後の持続稼働、rollback。増築可能なHost差分と共通契約。
2. **S3:** G:大容量保存の認可付きファイル操作/容量表示/USB切断保護。Windows F:とG:のMount実体を必ず区別し、実原本の上書き/移動なしでE2E。
3. **S4:** `seigo-gace/gace-dev-kb` の既存MVS（BM25/Vector/Hybrid/KG/MCP）・単一Current・ModuleCatalog/ACCEPTED/ACTIVE・rollbackを再利用してGserverへ段階統合。既存インデックス/履歴/資料を壊さない。旧`kb-system`へ逆戻りしない。
4. **S5:** 既存Contabo **TGserver ZERO/vNext** の**稼働が確認できたAPI契約**にGserverのWeb/Bot/KB logs（event_id/受領/原文/検索）を接続。TGS不通時は容量上限付きspool＋再送と曖昧な受領の照合。G:・KBからmanifest/SHA-256/AEAD暗号/鍵分離バックアップ→実送信/実取得/復号/整合性検証/隔離復元。**vNext構想だけのAPIを実装済みと誤認しない**、TGSを単なる通知Botとして作り直さない。Contaboの本番TGS・secret・設定変更は今回の単発許可の範囲外。認可不要なソース/API調査とローカルスタブ/契約テスト/Adapter実装は進める。
5. **S6/S7:** 無駄なOSS追加をせず監視/権限/リソース/障害回復/事故時の逆引き、非技術者操作のUI、GitHub遮断・TGS切断・電源/WSL/USB障害の安全な実機受入、隔離復元・データ保護・長時間試験と証拠。できた部分だけACCEPTED、未検証は未完了。

## 6. 守る境界・継続規則

- **Masterから承認済み:** このGserver対象範囲での通常コード編集、デバッグ、ローカルisolated Docker検証、テスト、必要なGitHubブランチ/PR/安全なマージ・読戻し、Issue Current更新。失敗時は原因調査→修正→再検証し、区切りごとに回答待ちで止めない。
- **別承認が必要:** 既存Web/Bot/KB/TGS本番の停止/公開設定変更、Contabo Host操作/本番TGSデータへの送信、Windows設定・F:/G:実データの移動/削除/上書き、暗号鍵/機密の移行、Public→Private切替、費用/権限/設計目的に実質的影響のある操作。**安全に独立して進められる開発は続ける**。
- **禁止:** 未許可の別Agent/ServerAI、Codexの時間指定/定期自動タスク、無制限バックグラウンドCodex、GitHubへの`@codex`コメントや自動PRレビュー、新MCP/Workflow/Token、Docker socket露出/無制限port publish、root/特権常用、既存PodmanやaaPanel/Redisの無断停止、`docker prune`や危険な`rm`/reset、secret/設定ファイル本文の公開GitHub投稿。追加有料モデル・多重推論エージェントは起動しない。
- コストと再現性: 同じテストを無意味に反復せず、モデル生成よりローカルスクリプト・CI・実ログ/ソースの調査を優先。Docker image/versionは本番ではdigest pinなど再現可能な依存固定。既存テストを破壊せず、バグ原因が分かる回帰テストを追加。
- 報告は**簡潔に日本語で事実のみ**。GitHub Issue #9と `docs/CURRENT.md` に、重要な進捗でTask ID/Owner/Source SHA/実Host状態/テストと未確認/rollback/次の最小未達項目を更新。Notion更新やGPT CHAT用5部報告はCodexの仕事ではない。Project #1 Itemの実体確認は必要時だけ。
- ユーザーの操作はできる限り不要。**どうしても本人操作/管理者認証が要る場合**は実行済み作業と残作業を分離し、1回で使える完成済みコマンドを1ブロックで示す。ユーザーにコード編集/調査/コマンド組立を頼まない。
- 完了したと言えるのはF01～F08の実PC/復元証拠が揃った場合だけ。途中時点で実環境や承認が限界なら、**完成したSource/テスト/コミットを残し、阻害要因と続きのExact Nextだけ**をCurrentへ明記する。勝手に非同期の継続作業を予約しない。
