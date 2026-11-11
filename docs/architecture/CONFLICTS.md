# Gserver設計の衝突／不明点
古いNotion設計は歴史資料。採用判断前に現物と照合し、未検証をPASSにしない。

| ID | 問題 | 関連タスク |
| --- | --- | --- |
| C01 | 旧kb-systemを現行G-ACE Dev KBと混同 | S0-01 / S4-01 |
| C02 | F:は固定KB専用か移行元か（採用：移行元、原本保護） | S1-01 / S4-02 |
| C03 | G:試験PythonとLinux正式コード配置の衝突 | S1-04 / S2-01 |
| C04 | nginx/aaPanel/siteと別Python Web入口の二重化 | S1-03 / S2-03 |
| C05 | KB Windows watcher/inbox/journal/rollbackが以前のFileTreeに未反映 | S4-01 / S4-04 |
| C06 | kb-systemとgace-dev-kbの未整理の利用者・機能差 | S4-01 |
| C07 | TGS ZERO/vNextの実API/デプロイ版不明 | S1-06 / S5-03 |
| C08 | Windows/WSLのNode/Python共用・重複認識 | S1-02 / S2-02 |
| C09 | Windows起動とWSL/systemdの自動復帰未実証 | S1-07 / S2-04 |
| C10 | Firewall/入口/認証/権限/公開面未監査 | S1-03 / S6-01 |
| C11 | TGSへ保存＝復元可能、との誤認 | S5-04～06 / S7-03 |
| C12 | Notion FileTree/擬似コードを現行実装と誤認 | S0-03 / S1-04 |
| C13 | PC全資産・利用中サービスの依存表不完全 | S1全体 / S7-05 |
| C14 | CPU/RAM/IO、24時間運用SLO未実測 | S6-04 / S7-04 |

## コンテナ主体の決定で解消/進行する既存衝突（2026-10-23）

C03/C04/C08/C09は、旧Python単独常駐やaaPanelを本番の既定に固定せず、**Docker Engine + Docker Compose主経路への段階移行**で扱う。Windows側は最小Host、WSL Docker Host上にサービスを分離し、既存Contabo Dockerとの運用契約を統一。現時点でGserverのDocker未導入は**未達の実装項目**であって、Podman採用・Docker廃止の決定ではない。サービス/データ/volume/port/rollbackを実証するまで対象衝突を解消済みにしない。追加Hostや外部公開、新しい管理サーバー・Tokenを無断作成しない。


衝突解消は『既存実体→再利用→採用差分→影響→回帰・復元→証拠』で判断。既存データ/PCサービスの無断削除は禁止。

## 2026-10-30 責務訂正（F02/F05/F07）

BotログのGateway→TGS転送を汎用Host完成と混同していた優先判断を訂正。独立アプリは各Composeプロジェクト、Coreは既存API/Storage、TGserverは遠隔ログ/バックアップを所有する。Bot API/spool/Workerは互換資産として保持し、基本利用を妨げる実害がない限り分離・整理を後段へ置く。PR #15を再利用し、Coreを再配置せず独立アプリ共存を検証する。Cloudflare/VPNの採用・外部公開は別判断。既存volume内pendingイベントを削除・再送しない。
