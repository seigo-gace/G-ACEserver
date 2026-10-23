# PC実コードのGitHub移行｜制約と順序
**SOURCE_IMPORT=PENDING。** GitHub側で設計・タスクの登録はできるが、ChatGPTのGitHub接続はローカルWindows/WSL内のソースを自動的に読み取る権限ではない。

1. 既存VS Code「WSL: Ubuntu」内でCodexが既に使えているかを**再インストールなし**で確認する（今の同期アカウントを維持）。
2. Gserverの既存ソース、Windows／Ubuntuサービス起動経路、フォルダの重複、Git管理、現行ブランチをread-onlyで確認。
3. F: G-ACE KB原本、G:データ、既存バックアップの保存と現在のOwnerを同定。破壊・コピー後の上書き禁止。
4. このRepoの内容と現行PC上のソースを比較。実ソースを公開してよいものだけ別変更で取り込み。**資格情報、.env、ログ、実データ、鍵、私的PC情報は登録しない**。
5. 既存Web/KB/TGSのAPI契約とソース差分を作成し、PC実Runtime、CI、バックアップ・復元試験を分けて証拠化。
6. 動作中のアプリ/プロセスを即停止しない。Git上のFileTreeを既存ソースに合わせて段階的に更新する。
7. 既存Contabo VPS経路（Actions→Host）をGserverへのリモート接続として勝手に使わない。新規Workflow/Token/MCPを作らない。

## 移行状態
| 層 | 内容 | 判定 |
| --- | --- | --- |
| 設計 | 要求8、46タスク、アーキテクチャ、リスク | GitHub文書へ移行 |
| ローカル実コード | 試作Python、nginx/aaPanel、その他 | 未取得 |
| KB原本 | F: / G-ACE Dev KB runtime | 未取得（外部GitHubソースは照合済み） |
| TGS実連携 | 別サーバーの実APIとGserverからのreadback | 未実証 |
| 本番・自動起動 | Windows/WSLサービス・再起動 | 未実証 |
