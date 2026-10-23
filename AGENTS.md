# G-ACEserver｜Codex 実行入口
## 読込順
1. [README.md](README.md) → [docs/CURRENT.md](docs/CURRENT.md) → 今回の GitHub Issue／[46タスク](docs/tasks/S0.md)
2. [G-ACE server-core Manifest](https://github.com/G-ACE-inc/server-core/blob/main/operations/github-project-rule-plane.json) → [SERVER_AI #16](https://github.com/G-ACE-inc/server-core/issues/16) → アクセスできる場合のみGitHub Project #1 のGserver Current
3. 作業対象の既存コード／テスト／必要な設計だけ。GPT CHAT用の長文Rule #17はCodexへ読み込まない。

## 目的・禁止
- 対象は**ユーザー手元のWindows PC＋WSL Ubuntu**。Contabo VPSと混同しない。
- GserverはWeb・Bot・G:ストレージ・既存G-ACE Dev KB・既存TGS連携を統合するサーバー。完成は実PC E2Eと復元で判定。
- PC側では既存VS CodeのWSL: Ubuntu接続と、ユーザーが使用中のCodex認証／同期を利用。CLI/拡張/アカウント/トークンの二重導入禁止。
- CodexはMaster/CHATから明示された作業範囲だけ実行。Server AIの限定リソース使用判断・追加有料モデル投入はMasterが行う。勝手に起動しない。
- 既存nginx/aaPanel、[G-ACE Dev KB](https://github.com/seigo-gace/gace-dev-kb)、TGserverの実装を調べて再利用。旧kb-systemと現行Dev KBを混同しない。
- 現在のリポジトリは**公開**。実機の内部アドレス／ホスト固有情報／個人データ／認証情報／インシデントログ／バックアップ鍵をコミットしない。
- F:のKB原本、G:のデータ、旧Currentやrollback、既存依存サービスを保護。実装・配置を推測して上書き／削除しない。
- 新規MCP/Workflow/Token/兄弟worktree/重複サービスを勝手に作らない。GitHub Projectへの登録済みやHost経路の利用権限は推測しない。

## 1タスク実行
対象Issueの完成要件→現物の読取/競合把握→既存再利用→必要な設計差分/コード→重点テスト→PC実測→rollback→Issue/CURRENTの更新。依存タスクが未完でも、安全で独立な実装を停止しない。
事実/推測/未確認、Source/CI/PC Runtime/TGS Readbackを別ステータスにする。/healthの200やCI成功を全体完成と呼ばない。
単一タスクの途中で細切れ報告停止を繰り返さない。主な作業単位がまとまるところまで継続する。
