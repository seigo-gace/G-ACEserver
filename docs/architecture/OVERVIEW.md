# Gserver全体構造｜ターゲット
**論理設計。実PCの現行FileTree/稼働証拠ではない。**

```text
Windows PC Host (電源・Defender/Firewall・VS Codeのみを基本)
└─ WSL Ubuntu (D:上のLinux仮想ディスク)
   ├─ Host境界: Docker Engine + Docker Compose (導入/運用未検証)
   │  ├─ Web ingress / 認証 / Web UI・API コンテナ群
   │  ├─ G:向け認可付きStorage adapter コンテナ
   │  ├─ 既存G-ACE Dev KB/MVS/ModuleCatalog受領コンテナ群
   │  │  └─ BM25/Vector/Hybrid/KG/MCP・単一Current・rollback維持
   │  ├─ TGSクライアント/ログ転送・backup job と有界spool
   │  └─ 必要最小限の監視・独立したサービス（将来拡張）
   ├─ Host境界: systemd / Docker起動 / mount / Firewall / 許可されたsecret注入
   ├─ G: 大容量データ・backup (永続volumeの原本; imageに内包しない)
   └─ F: Dev KB移行元・既存Currentを非破壊に保護
別Host: 既存Contabo Ubuntu + Docker/Compose → TGserver等の既存サービス
将来: 追加HostもDocker/Composeの同じ運用契約で参加 (Host固有設定は別)
```

## コンテナ・複数Host共通契約（Master確定／Gserver実機未導入）

- **Docker-first**：GserverをLinux/WSLのコンテナHostとして構築し、サービス単位にDocker Engine + Composeで増減・個別起動/停止/更新/rollbackできるようにする。既存ContaboもDocker＋Composeを使用しており、ホストOSや保存領域は違っても共通の運用手順に揃える。Docker廃止・Python単体常駐への恒久化・Podmanへの置換は採用しない。
- **同じものにする範囲**：Compose構成・命名・healthcheck/readiness・least privilege/非root・コンテナ間の内部network・外部公開範囲・resource上限・ログ/メトリクス・永続データvolume・version固定・状態復旧/rollback・バックアップ検証。サービスごとに増築可能な独立性を優先し、HostごとのUSB/ドライブ・CPU/RAM・公開Ingress・secret/ネットワーク設定は差分として扱う。
- **疑似Cloudの実態**：複数Host上で同じ手順によりアプリを追加/更新/運用するセルフホスト基盤。既存のG-ACE Projectは開発/変更管理の正本とし、Gserverの通常動作をGitHub/APIに依存させない。初期段階でKubernetes/Swarm、新しい制御サーバー、MCP/Workflow/Tokenを設置しない。将来の一元状態表示/操作は既存機能を再利用し、実際の複数Host利用時に別途権限/到達性を検証する。
- **ホスト共通化 ≠ サービス横取り**：Contaboの稼働中コンテナ・TGserver・Host権限をGserverから勝手に変更/統合しない。別Hostは独立運用し、デプロイ・認可の境界を越えない。Telegram関連5資産の採否は別作業。
- **安全な段階移行**：PCでは`docker`未検出、Podmanは存在、Redis/site_total/aaPanelおよび109行Copilot HTTP試作は現行サービス/資産として残っている。Docker導入後も既存稼働は即停止せず、別ポート/別コンテナでビルド→健康確認→実依存・データ境界の確認→切替→rollbackの順に進める。`/srv/gserver`の作成やF:原本移動を先行条件にしない。
- **データと秘密**：F:の原本・Current/索引、G:の保存・TGS spoolはimageへ焼込まない。許可されたホストvolume経由で永続化し、mount失敗時はfail closed。Docker socket/Host rootや秘密をアプリコンテナに与えず、公開RepoにPC固有の機密を入れない。container health成功だけでKB/TGS復旧受入をPASSにしない。


## 実行面と開発面の分離（採用）

**開発・配布面：** GitHub Project / Issues / PR / CI / committed Sourceは変更管理と必要時の更新物配布を担当する。停止していても既存Gserver Runtimeを止めない。

**手元PC実行面：** Windows起動→WSL/既存Web入口→Web/API/Bot、G:認可付きStorage、ローカル受領済みDev KB/索引/単一Current、TGS向け有界spoolで構成。通常の処理はGitHubのOAuth/API/Actions/clone/fetchに依存させない。

**既存KB：** Git履歴は知識出典として有効。新履歴の取得とローカル索引/Current検索は独立した責務であり、通常検索のために毎回GitHubへ通信しない。ModuleCatalogの既存受領/ACCEPTED/ACTIVE/rollback機能は再実装しない。

**別HostのTGS：** 遠隔ログ/バックアップの送受信にはTGS通信を要する。切断時にはGitHubへ代替送信せず、ローカル機能の継続、spool容量制限、未送信状態を分ける。TGSの復旧確認はF05/F08に残す。

**検証境界：** S1でコード実体と通信依存を観測し、S7でGitHub切断状態のPC実機E2Eを検証する。現時点は設計のみ、稼働確認は未完了。Repo Private化は完成後の別ゲート。

## コンポーネント単位の責務
Web公開はまず既存サイト入口とaaPanel等の実依存を絞って確認し、最終系はDocker/Composeで必要なingress機能を保持する。未使用のaaPanelを恒久的な必須基盤として残さず、安全な置換/撤去は依存と退行を確認してから行う。Python HTTP試作は暫定であり、コンテナ化の対象か採用不要かを判断する。KB検索エンジンは新規作成しない。TGSは通知Botの新設ではなく既存ZERO/vNextと実APIを照合。WindowsとWSLのランタイムは互換バイナリと誤認せず必要なOS版を選び、Windowsで使わないものだけ整理する。
監視はOS標準と既存Webから開始し、CrowdSec（防御候補）、Beszel（リソース監視候補）、Uptime Kuma（死活監視候補）から不足機能に適合する最小部品のみ採用。どれも未導入候補であり、導入済みとしない。
`docs/tasks`に46単位の実行計画、`docs/architecture/CONFLICTS.md`に衝突台帳、`docs/architecture/TRACEABILITY.md`に要求追跡を置く。

## Telegram関連5資産の保留グループ（Master決定、Gserver開発から分離）

以下は、G:上で見つかった独立したTelegram系候補の**一つの管理グループ**として扱う。新しいGserverの機能として採用済みと誤認しない。

- `GateApp-Bot`
- `TGbot_grp_system`
- `reserve_order_bot`
- `guard_full_userbot`
- `gacebot-profile`

用途の確認・再利用・統廃合判断は**別作業**で行う。それまでGserverの統合・移設・依存チェック・新Bot実装の前提から除外し、既存のGit管理と起動パス/ログ/venvを変更しない。PCで一か所に見せる必要がある場合は、既存の実フォルダは移動せず、独立した閲覧用ショートカットだけをまとめる（実際の作成・動作はPCで別途検証）。これは既存F02の「複数Bot独立運用」という最終受入要件を変更せず、**どのBotを使うかの採用決定を保留するもの**である。

放棄された旧`kb-system`はこのグループに含めず、正式KBは`seigo-gace/gace-dev-kb`とする。

## ファイル配置方針
Compose定義・実行コード/image build設定はLinux FS上で管理、コンテナ内実行依存はimageに閉じる。状態DB/索引/ログ/spoolはホスト要件に適した永続volume、G:は大容量データ、F:は原本。旧G:試験コードと提案されたLinux配置の実一致は不明なのでS1で現物確認後にFileTreeを確定。実行プロセス・port・秘密値は公開Repoへ記載しない。
