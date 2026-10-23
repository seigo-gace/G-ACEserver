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

タスク: [S0](../tasks/S0.md) / [S1](../tasks/S1.md) / [S2](../tasks/S2.md) / [S3](../tasks/S3.md) / [S4](../tasks/S4.md) / [S5](../tasks/S5.md) / [S6](../tasks/S6.md) / [S7](../tasks/S7.md)。
