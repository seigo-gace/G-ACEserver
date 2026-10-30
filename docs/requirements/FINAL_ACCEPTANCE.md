# Gserver 最終完成条件｜F01～F08

## 2026-10-31 通信保護の必須要件（F02/F06/F07/F08）

保護対象appのBot API/媒体/関連通信とcloudflared→Cloudflare接続をWindscribe WireGuard日本通常/韓国予備へ固定し、自宅IPの不要な露出を防ぐ。Firewall/Kill Switch・DNS/IPv6/Proxy漏洩防止、Webhook認証・Cloudflare既存防御維持、Vault正式契約/暗号化/鍵保護、攻撃隔離・復旧・必要速度を全て実証する。[統合設計v3](../handoffs/TELEGRAM_VPN_PRIVACY_2026-10-30.md)のGateを適用。速度未達・漏洩未検証・VPN断のdirect fallbackは不合格。Gserverは汎用Host、独立appを専用Coreへ組み込まない。Contaboは今回不使用。F05の正式バックアップ要件は維持し、今回未実施を消さない。

文書状態：GOAL FIXED / CORE・STORAGE一部実機PASS / 全体受入未完了。

## 2026-10-30 目的・受入の補正

Gserverは独立アプリを運用する汎用Compose Host。Telegram Bot/Tumblrの機能とGserver基盤、TGserverのログ/バックアップ責務を分離する。F02の直近受入は個別アプリの起動・停止・状態/ログ・共存・永続化・更新/復旧。既存Core/認証/G:マウントとStorage ready/filesはOwner実機PASS。独立アプリとWindows→WSL→Docker復帰は未受入。Gateway/TGS、Cloudflare、送信元IP秘匿用VPNをローカル利用の必須依存にしない。基本利用開始とF01〜F08全体完成を別判定とし、後段のF04/F05・障害復元要件も維持する。

## Master運用・保存先の確定補正（2026-10-28）

- **唯一の管理利用者はMaster本人。** Gserverの管理・保守は既存の **VS Code / Cursor からWSL Ubuntuへ接続し、Terminal / CLI / Compose** で行う。管理者向けWebダッシュボードの新規開発・画面拡張・ブラウザE2Eは完成要件ではない。すでに作ったUIは廃棄のための作業を増やさず、依存がなければ維持してよいが、今後の優先開発・受入をUIに寄せない。Web/API機能自体は必要な製品機能として維持。
- **C: SSD（公称約118GiB）はWindows最小運用に限定。D: HDD内の既存 `D:\WSL\Ubuntu` にWSL2の `ext4.vhdx` は移設済み。** 無断でWSLを再移設・新規インストール・二重登録・削除しない。Docker Engine/ComposeもこのWSL内に導入済み。Linux Dockerの現物 `/var/lib/docker`, `/var/lib/containerd` の配置・使用量、Windows側のVHDX保存先、C:/D:空き容量を**read-onlyで照合**してから、新しい重いimage/build/cacheを増やす。Docker Engine v29のcontainerd image storeを見落とさない。
- **速度優先と容量保護の両立:** D:はHDDなのでSSDと同等の速度ではない。Linuxビルド/Git/npmの高頻度I/OをWindows driveマウント(`/mnt/d`/`/mnt/g`)越しに走らせる速度問題と、D:上のWSL ext4内で走らせる性能を混同しない。ホットなコード/一時ビルドは既存WSL ext4領域を優先しつつ、現有Gserver親Project/Repoの正本・既存配置・Parent Worktree境界を守り、計測・差分確認なしで複製や移動しない。G:は既存資産/容量データ、F:はKB原本の保護を継続。
- **C:容量について:** Masterの最新申告は「約117GB表示、空き約36GB」。既往のC:空き約34～35GBと近いが、今回DockerによるC:増加を実証していない。空き36GBを無条件に安全・危険と決めず、Windows update/一時ファイル/VS Code/Cursor/WSL関連の用途別増加を差分測定し、容量を食う追加機能・二重runtime・Web UIの構築を避ける。**原本/キャッシュ/volumeを推測で消さない。**
- F01～F08/既存46タスクの番号を変えず、旧タスク文中「管理UI必須」や「UIボタン操作」は今回のMaster明示決定を優先して **CLIの操作・復旧導線による受入**に読み替える。HTML UI維持のためのCI・依存追加・工数は不要。安全・認可・復元/証跡の要件は緩めない。


| ID | 完成地点 | 受入条件 |
| --- | --- | --- |
| F01 | C:はWindows最小Host、D:のWSLでWeb/Bot/KBを稼働し、WindowsとLinuxに不要なNode/Pythonを二重常設しない | 実行依存の照合、実OS起動、冗長プロセスなし |
| F02 | 必要なWeb/APIと既存Botの独立運用。管理はVS Code/Cursorのターミナル/CLIを第一経路とし、Web管理画面は必須としない | CLIで起動・停止・変更・状態/ログ確認・失敗復旧を行えること、必要なWeb/API/Botの実動作 |
| F03 | G:大容量の認可付き保存と、F:にある既存KB原本の保護 | 一覧/送受信/更新/削除/容量管理、USB断・権限外操作の防御 |
| F04 | G-ACE Dev KBのGserver移行、既存MVS（BM25/Vector/Hybrid/KG/MCP）と単一Current、ModuleCatalog受領、Rollback/Deep Healthの維持 | コピー・索引・検索・受領/ACTIVE・旧履歴・復旧のE2E |
| F05 | TGSにWeb/Bot/KBログ原文、検索索引、ファイル・暗号化バックアップを保存 | TGS実送信→実ダウンロード→SHA/復号→隔離復元 |
| F06 | Windows/WSL/Web/Bot/KB/TGSの安全運用と省リソース監視 | 既存防御＋必要最小OSS、起動/通知/回復、CPU/RAM/IO実測 |
| F07 | 人間/AIが障害とコードを追跡できる責務・ファイル・依存マッピング | 症状→サービス/ポート→コード→ログ→テスト→rollbackの逆引き |
| F08 | 全機能の完成・障害復元を実PCで実証 | Source/CI/Runtime/Backupsを別証拠として全必須Gate ACCEPTED |

## 横断必須条件：Docker/Compose-firstで複数Hostに展開可能（Master確定）

- **F01/F02**：Gserverの本番アプリ/サービスは原則Dockerコンテナとして分離し、Docker Engine + Docker Composeによる作成・設定・起動・停止・更新・再起動・rollbackを可能にする。Windowsは最低限、Linux実行環境はWSLへ。Host側OS起動・mount・Firewall・Docker daemonだけをHost責務とし、例外のHostネイティブ常駐は実測依存/理由/Ownerを明示する。
- **F02/F06/F07**：サービス毎のCompose構成、health/readiness、内部network/公開Port/認証、最小権限、CPU/RAM制限、永続volume/secret、ログと障害からの復旧をHostを跨いで同じ運用契約で管理する。追加ServerはContabo等を前提とするが、実機承認・アクセスは各Hostで個別に扱う。コンテナの移設・新規サービス追加で既存Serverの稼働が壊れないこと。
- **F03/F04/F05**：コンテナの再作成やimage更新後もF:の原本、G:の実データ、既存Dev KB単一Current/rollback、TGS向けspoolとbackup証跡を失わない。volumes/mountと接続失敗は安全側に倒す。既存Contabo側Docker/TGSの変更を必須にしない。
- **F08**：Gserver実PCでDocker/Composeの起動/再作成/別版差戻し、永続性、GitHub切断下の通常運用、Host固有設定と共通Compose契約の分離を実測して受入。将来Hostを実際に増設していない状態で「複数Host稼働済み」と捏造しない。Docker未導入であれば本条件はNOT_VERIFIEDのまま。
- Kubernetes/Swarm/新たな集中コントロールプレーンの導入は現段階の必須条件ではない。**この方針でF01-F08を置き換えたりStage/タスクを増やさない。**


## 横断必須条件：GitHub非依存の通常運用（Master決定／実機未検証）

F01〜F08の既存番号に含める。別の製品機能や追加Stageは作らない。

1. **F01〜F04/F06：** GitHub接続、GitHub OAuth/API/Actions、GitHubへのclone/fetchがなくてもWindows/WSL起動、Web/API、Bot、G:の認可付きファイル操作、既存KB検索・単一Current・ローカル復旧が使えること。新バージョン取得・新Git履歴取り込みは通常利用と別の更新操作にする。
2. **F04：** Git由来履歴のSource/Commit SHAを失わず、受領済みローカル資料と索引でBM25/Vector/Hybrid/KG/MCP検索、Deep Health、rollbackを行う。既存のModuleCatalog受領/ACTIVE契約を変えない。
3. **F05：** TGSとの実通信はGitHubとは独立した外部依存。TGSが使えない間は保管上限付きspoolと未送信/失敗状態を持ち、復帰後の再送・読戻し・隔離復元を別途実証する。TGS障害中のF05をPASSとしない。
4. **F08：** PCでGitHubへの通信だけを遮断し、既存のWindows/WSL起動・Web/API/CLI・Bot・Storage認可・KB検索/Current/ローカル復旧を代表操作で実証する。GitHubに接続した通常時との差分を記録し、TGSとの接続状態を混同しない。遮断試験未実施なら最終受入は未完了。
5. **完成後の出口：** F08受入後、公開Repoに秘密/個人データ混入がないことと既存連携への影響を監査し、GitHub RepoをPrivate化して設定を読戻す。それまではPUBLIC / PRIVATE_PENDINGと記録する。

ここに記載した内容は採用済み要件であり、既存PCコードの適合、GitHub遮断試験、Private化の実施証拠ではない。

タスク: [S0](../tasks/S0.md) / [S1](../tasks/S1.md) / [S2](../tasks/S2.md) / [S3](../tasks/S3.md) / [S4](../tasks/S4.md) / [S5](../tasks/S5.md) / [S6](../tasks/S6.md) / [S7](../tasks/S7.md)。
