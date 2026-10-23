# PC実コードのGitHub移行｜制約と順序
**SOURCE_IMPORT=PENDING。** GitHub側で設計・タスクの登録はできるが、ChatGPTのGitHub接続はローカルWindows/WSL内のソースを自動的に読み取る権限ではない。

1. 既存VS Code「WSL: Ubuntu」内でCodexが既に使えているかを**再インストールなし**で確認する（今の同期アカウントを維持）。
2. Gserverの既存ソース、Windows／Ubuntuサービス起動経路、フォルダの重複、Git管理、現行ブランチをread-onlyで確認。
3. F: G-ACE KB原本、G:データ、既存バックアップの保存と現在のOwnerを同定。破壊・コピー後の上書き禁止。
4. このRepoの内容と現行PC上のソースを比較。実ソースを公開してよいものだけ別変更で取り込み。**資格情報、.env、ログ、実データ、鍵、私的PC情報は登録しない**。
5. 既存Web/KB/TGSのAPI契約とソース差分を作成し、PC実Runtime、CI、バックアップ・復元試験を分けて証拠化。
6. 動作中のアプリ/プロセスを即停止しない。Git上のFileTreeを既存ソースに合わせて段階的に更新する。
7. 既存Contabo VPS経路（Actions→Host）をGserverへのリモート接続として勝手に使わない。新規Workflow/Token/MCPを作らない。

## GitHub切断を前提とする運用設計（採用／未検証）

GitHubは開発・更新管理のみに使用する。Gserver実行コードの起動/ログイン/通常操作/KB検索/復旧の経路にGitHub API・認証・Actions・clone/fetchの必須呼出しがないかS1-04で限定確認する。見つかった依存は既存ローカル資料・索引・設定を活用して通常運用から切離す。出典Git SHAは保持し、資料更新時に新履歴を入手する操作まで禁止しない。

Gserverの実PCでGitHub通信を遮断したE2E結果が出るまでOFFLINE_RUNTIME=NOT_VERIFIED。TGS障害時は未送信/有界spoolとし、GitHubを代替配送路にしない。完成後のRepo Private化はPRIVATE_PENDING。

## 読取専用PCソース調査の入口（GSR-S1-04／PC未実行）

既存のWSL Ubuntuとインストール済みPython 3のみ使用する。Codex、追加トークン、GitHub通信、サービス停止を必要としない。GitHubからソースを入手済みの作業場所で実行するコマンド：

    python3 scripts/pc_gserver_inventory.py

過去の設計で言及された2箇所と、既存調査に現れた限られた上位フォルダ配下のGserver名ディレクトリだけを浅い階層・件数上限付きで対象に、対象コードの相対パス・SHA256・GitHub関連の要確認行番号/分類を**ローカル**の ~/.local/state/gserver/pc-source-inventory-*.json に保存する。ファイル本文・秘密・ログは収集せず、公開Repoには結果をコミットしない。存在しない/読めないパスはそれぞれ未確認として扱い、ほかの実コードまで不存在と断定しない。これはSourceの一次棚卸し用であり、PC RuntimeやGitHub遮断E2Eは別途要検証。

テストは通常の開発環境で python3 -m unittest discover -s tests -v を使用。現PC上の実行は未確認。

## 移行状態
| 層 | 内容 | 判定 |
| --- | --- | --- |
| 設計 | 要求8、46タスク、アーキテクチャ、リスク | GitHub文書へ移行 |
| ローカル実コード | 試作Python、nginx/aaPanel、その他 | 未取得 |
| KB原本 | F: / G-ACE Dev KB runtime | 未取得（外部GitHubソースは照合済み） |
| TGS実連携 | 別サーバーの実APIとGserverからのreadback | 未実証 |
| 本番・自動起動 | Windows/WSLサービス・再起動 | 未実証 |
