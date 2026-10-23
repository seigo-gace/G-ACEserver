# 完成条件・実装・障害トレーサビリティ
| Requirement | Component | Related tasks | 受入証拠 |
| --- | --- | --- | --- |
| F01 | Windows Boot/WSL/Runtime | S1-02/07; S2-02/04 | 実起動・二重常駐解消 |
| F02 | Web/nginx/API/UI/Bot | S1-03/04; S2-03; S3-01/05; S5-01 | 独立サービス・UXとE2E |
| F03 | G: storage adapter | S1-01/04; S3-02..05 | 認証/転送/SHA/脱着安全 |
| F04 | G-ACE KB MVS/Current | S1-05; S4-01..06 | ACTIVE+rollback/MCP/Deep parity |
| F05 | TGS producer, backup client | S1-06; S5-02..06 | 同一イベントraw/index+隔離復元 |
| F06 | OS/OSS防御・監視 | S1-07; S6-01..06 | 公開面/通知/復旧/資源 |
| F07 | Registry/evidence map | S0全体; S7-05 | 症状→Component→File→Test→Rollback |
| F08 | Final Acceptance | S7-01..06 | 同時運用・負荷・障害・復元PASS |

## デバッグ対応表に必須の列
TASK_ID / COMPONENT_ID / SYMPTOM / DEPENDENCIES / PROCESS_OR_SERVICE / SOURCE_PATH+SHA / CONFIG (redacted) / DATA_STORE / LOG_ID / TEST_COMMAND+EXIT / ROLLBACK / OBSERVED_STATUS / OWNER。

実機の内部情報とセキュリティ証跡は公開GitHubへ貼らず、閉域で保管。GitHubには秘密のない要約と証拠照合IDを置く。
