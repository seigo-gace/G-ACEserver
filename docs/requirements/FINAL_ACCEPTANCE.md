# Gserver 最終完成条件｜F01～F08
文書状態：GOAL FIXED / RUNTIME NOT VERIFIED。

| ID | 完成地点 | 受入条件 |
| --- | --- | --- |
| F01 | C:はWindows最小Host、D:のWSLでWeb/Bot/KBを稼働し、WindowsとLinuxに不要なNode/Pythonを二重常設しない | 実行依存の照合、実OS起動、冗長プロセスなし |
| F02 | nginx/aaPanel等既存資産の再利用とWeb/API/管理UI/複数Botの独立運用 | UIの戻る/変更/失敗復旧を含む実利用操作と同時稼働 |
| F03 | G:大容量の認可付き保存と、F:にある既存KB原本の保護 | 一覧/送受信/更新/削除/容量管理、USB断・権限外操作の防御 |
| F04 | G-ACE Dev KBのGserver移行、既存MVS（BM25/Vector/Hybrid/KG/MCP）と単一Current、ModuleCatalog受領、Rollback/Deep Healthの維持 | コピー・索引・検索・受領/ACTIVE・旧履歴・復旧のE2E |
| F05 | TGSにWeb/Bot/KBログ原文、検索索引、ファイル・暗号化バックアップを保存 | TGS実送信→実ダウンロード→SHA/復号→隔離復元 |
| F06 | Windows/WSL/Web/Bot/KB/TGSの安全運用と省リソース監視 | 既存防御＋必要最小OSS、起動/通知/回復、CPU/RAM/IO実測 |
| F07 | 人間/AIが障害とコードを追跡できる責務・ファイル・依存マッピング | 症状→サービス/ポート→コード→ログ→テスト→rollbackの逆引き |
| F08 | 全機能の完成・障害復元を実PCで実証 | Source/CI/Runtime/Backupsを別証拠として全必須Gate ACCEPTED |

## 横断必須条件：GitHub非依存の通常運用（Master決定／実機未検証）

F01〜F08の既存番号に含める。別の製品機能や追加Stageは作らない。

1. **F01〜F04/F06：** GitHub接続、GitHub OAuth/API/Actions、GitHubへのclone/fetchがなくてもWindows/WSL起動、Web/API、Bot、G:の認可付きファイル操作、既存KB検索・単一Current・ローカル復旧が使えること。新バージョン取得・新Git履歴取り込みは通常利用と別の更新操作にする。
2. **F04：** Git由来履歴のSource/Commit SHAを失わず、受領済みローカル資料と索引でBM25/Vector/Hybrid/KG/MCP検索、Deep Health、rollbackを行う。既存のModuleCatalog受領/ACTIVE契約を変えない。
3. **F05：** TGSとの実通信はGitHubとは独立した外部依存。TGSが使えない間は保管上限付きspoolと未送信/失敗状態を持ち、復帰後の再送・読戻し・隔離復元を別途実証する。TGS障害中のF05をPASSとしない。
4. **F08：** PCでGitHubへの通信だけを遮断し、既存のWindows/WSL起動・Web/UI/API・Bot・Storage認可・KB検索/Current/ローカル復旧を代表操作で実証する。GitHubに接続した通常時との差分を記録し、TGSとの接続状態を混同しない。遮断試験未実施なら最終受入は未完了。
5. **完成後の出口：** F08受入後、公開Repoに秘密/個人データ混入がないことと既存連携への影響を監査し、GitHub RepoをPrivate化して設定を読戻す。それまではPUBLIC / PRIVATE_PENDINGと記録する。

ここに記載した内容は採用済み要件であり、既存PCコードの適合、GitHub遮断試験、Private化の実施証拠ではない。

タスク: [S0](../tasks/S0.md) / [S1](../tasks/S1.md) / [S2](../tasks/S2.md) / [S3](../tasks/S3.md) / [S4](../tasks/S4.md) / [S5](../tasks/S5.md) / [S6](../tasks/S6.md) / [S7](../tasks/S7.md)。
