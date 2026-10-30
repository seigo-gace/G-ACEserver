# Gserver Telegram 送受信プライバシー強化｜Codex引継ぎ・検証台帳（2026-10-30 JST）

**STATUS: DESIGN/HANDOFF ONLY — IMPLEMENTATION=NOT_EXECUTED; HOST_TEST=NOT_VERIFIED.**
**Owner:** 既存 Gserver Current [Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9)、Codexの既存作業を尊重。別AIの新規起動を指示しない。
**Scope:** GserverローカルWSL/Dockerと関連Telegram通信。既存F01-F08／46タスクを変更せず、F02/F06/F07/F08に横断するセキュリティ差分。Contaboおよび共有サービス提供元の変更は対象外。

## 1. Mission / 確定インプット
自宅IPのTelegramおよび関連外部宛先への不要な露出を最小化し、**送信・受信・ファイル送受信**を保護し、速度・安全性・復旧性能を実測で比較する。「VPN接続できた」は完成ではない。

MasterがWindscribe Build A Plan の **日本 Tokyo - Shinkansen、韓国 Seoul - Hangang、無制限通信**を選択。手元で生成済みのファイル名:
- `Windscribe-Tokyo-Shinkansen-WG.conf`
- `Windscribe-Seoul-Hangang-WG.conf`

**課金確定・ファイル所在・実際の設定内容・WireGuard接続状況は、この引継ぎでは未確認。** WireGuard秘密鍵、PresharedKey、Bot TokenをGitHub/チャット/CI/logへ絶対に出さない。PublicKeyも設定構造の調査に不要であれば共有を要求しない。秘密はCodexの既存ローカル権限内でのみ読取・安全な権限設定を行う。

## 2. 重要な設計訂正
「Cloudflare Tunnelなら受信対策完了」は誤り。Tunnelは原点への直接公開を回避する経路であり、Telegram webhook真正性・認証・容量上限・公開域分離は別責務。TelegramのWebhook受信と `getUpdates` long polling受信は異なる。また `getFile` API/URLからのファイル受信は外向きHTTPSなのでVPN出口側の保護が必要。
- **Webhook受信**: Telegram → 所有権・用途承認済みのHTTPS入口 → 既存Tunnel/接続先 → Webhook認証・入力検証 → Bot。自宅直公開Port禁止。受信入口での公開URL・DNS・原点IP・TLS・認証・拒否応答・リプレイ/重複を検査。
- **Long polling受信**: Bot → VPN → Telegram API → 同じVPN内応答。専用公開入口不要。既存方式を調査し勝手に変更しない。
- **Bot API送信およびファイル送受信**: 対象Bot → 隔離Egress → WireGuard → Windscribe → Telegram API/ファイルホスト。直接WAN fallback禁止。
- **内部通信**: LAN/DB/Storage/既存Gatewayに必要な限定経路を維持。外部一般通信の抜け道を作らない。

**最優先の所有権制約**: server-core Rule Plane #17 (2026-10-30 現行) により、GserverのG-ACE側ドメインとAstera専用ドメインは別。既存Asteraゾーン、Tunnel、Gateway URLをGserver用途へ勝手に流用/変更/疎通送信しない。用途、正確なホスト名、影響に対してMasterの事前明示承認がないcross-zoneルートはFREEZE。既存のAstera資産を勝手に削除・再起動もしない。共有Webhook Gateway提供元の変更は別途明示承認が必要。Gserverへ許可された正規の受信入口を実測してから採用する。

## 3. 実装の判断フロー（先に現物確認）
1. Gserver Issue #9, `docs/CURRENT.md`, `docs/requirements/FINAL_ACCEPTANCE.md`, `docs/architecture/OVERVIEW.md`, `AGENTS.md` を読み、Codex既存変更/Worktree/Composeと所有者をread-only確認。CodexにはServer AI Rule #16を適用、CHAT用#17を負荷として渡さない。
2. 実際に稼働するTelegram Bot・Webhook/long polling・送信API・メディア取得/アップロード・外部URL取得・DNS解決・ログ・内部依存を通信フロー表に全数登録する。別案件の5つのTelegram資産の統廃合や移動は承認しない。
3. WSL2/Dockerの既存ネットワーク、IPv4/IPv6、NAT、Dockerブリッジ、host/コンテナFirewall、Tunnel ingress、プロキシ/環境変数を確認し、保護対象と非対象を分類する。
4. 第一候補は**Telegram送受信処理を壊さない独立Docker VPN egress Gateway**、日本通常・韓国予備。隔離netns共有（`network_mode: service:...`）は候補の一つ。Webhook inboundと内部サービスの互換性が崩れる場合はproxy/egress router等の別方式を比較し、**Botが直WANへ迂回できない**ことを実証できる方式を採用する。
5. Kill Switchをトンネル接続前に適用してDefault Deny。Windscribe VPNエンドポイントへの最小例外以外のWAN、DNS、IPv6、UDP、別インターフェースを遮断。例外が一般WANの抜け道にならないこと、DNS再解決/IP変更時の扱い、Docker再起動・WSL再起動の競合を試験。
6. Webhook入口は既存契約に合致する正規経路を使う。Telegram `X-Telegram-Bot-Api-Secret-Token` の安全な照合、HTTPS、サイズ/頻度上限、秘密の非表示、`update_id` 冪等性、接続切断時の扱いをテスト。TelegramのWebhook送信元IP固定だけに認証を依存しない。
7. 日本/韓国切替時は保護を解除せず、連続失敗/閾値/クールダウン/手動復旧を設け、切替前後に出口IPとルーティングをreadback。両方障害なら停止（fail closed）。切替自動化は実証・安全性確認後。
8. Windows全体にVPNを有効化しない。既存C/D/F/Gドライブ、Windows/WSL配置、Docker Image/Volumeと現行Gserverを保護し、無断の移動、prune、削除、重い二重ランタイム導入を避ける。

## 4. 受入試験と定量評価
| ID | テスト | 合格条件 | 現在の証拠 |
|---|---|---|---|
| IN-01 | 実WebhookまたはPolling方式の列挙 | 実Bot毎に方式/Owner/入口を特定 | NOT_VERIFIED |
| IN-02 | 正規Telegram Update受信 | 認証・重複排除・継続性が実動作 | NOT_VERIFIED |
| IN-03 | Webhook偽造/不正Token/過大Body | 拒否・秘密非漏洩・原点直公開なし | NOT_VERIFIED |
| IN-04 | Tunnel/入口停止・再開 | 自宅直公開fallbackなし・再同期成立 | NOT_VERIFIED |
| OUT-01 | 日本WG接続 | 実外向きIPがWindscribe出口、API成功 | NOT_VERIFIED |
| OUT-02 | 韓国WG接続 | 予備出口の実IP・API成功 | NOT_VERIFIED |
| OUT-03 | DNS/IPv6 | VPN外問い合わせ/IPv6外向きが不可 | NOT_VERIFIED |
| OUT-04 | VPN kill / 不成立 / 再起動 | 直接WAN成功0件、fail-closed | NOT_VERIFIED |
| OUT-05 | Endpoint/DNS/Proxy/別NICの迂回試行 | 非許可WAN到達0件 | NOT_VERIFIED |
| MEDIA-01 | getFile/送信メディア | ファイル取得とアップロードがVPN経由 | NOT_VERIFIED |
| PERF-01 | baseline vs JP vs KR | p50/p95遅延、送受信速度、失敗率、CPU/RAM/MTUを複数回測定 | NOT_VERIFIED |
| INTEG-01 | Tunnel inbound + VPN outbound | 両立し、既存Bot/Storage/内部API正常 | NOT_VERIFIED |
| OPS-01 | Docker/WSL再起動・Rollback | IP非漏洩、キュー/永続データ保持 | NOT_VERIFIED |

測定は対象経路・測定時刻・観測方法・使用出口・実際のRuntime出力を識別して残す。外部IPそのもの、自宅のネットワーク情報、秘密設定を**公開Repo**に載せない。性能閾値は基準値測定後に合理的に確定する。

## 5. 過去の試験データと証拠の階層
- **2026-10-30過去のCHAT内報告**: DebugAI隔離Branch `test/telegram-egress-isolation-20261030` の `tests/test_telegram_egress_isolation.py` および `tests/test_telegram_socks5_socket_probe.py` でオフライン模擬テスト（8/8、5/5 PASSとの過去報告）。**このGitHub引継ぎ作成時には再実行・commit/hash照合していない。過去報告扱い、実Host/WGの漏洩ゼロを示さない**。Source単体試験と実機試験を区別し、必要ならRepo内の実体を確認して再利用する。
- **Gserver Issue #9 / CURRENT**: 既存Bot・Gateway・TGserver統合に関するSource/Runtimeの別証拠あり（個々の時点・範囲を保持）。今回のWindscribe導入の実接続証拠ではない。
- この引継ぎ文書は **設計・テスト計画のGitHub保存**であり、VPNの購入/設定済み・Docker接続/漏洩試験成功の証明ではない。

## 6. Codexへの具体的な引継ぎ
既存Codexがこの文書を参照し、元のGserver Current/CUを再確認して**既存作業と競合しない単一Mutation Owner**を維持すること。既存Gserver作業を勝手に新しい「VPN専用Project」に移し替えない。Windows全体のWireGuard取り込みは実施せず、秘密設定ファイルはローカルに安全保管して利用する。

進め方：read-only棚卸し → 既存設計差分確認 → 送受信経路を分離設計 → 隔離実装/テスト → 実VPNでJP/KR検証 → 意図的切断/漏洩検証 → 動画転送性能比較 → 許可された範囲で既存Botへ段階統合 → rollback/restart/readback → Issue #9 と `docs/CURRENT.md` にSource/CI/Host/Runtimeを分離して記録。

**停止・承認境界**: Cloudflare別ゾーンの新利用/共有Gateway提供元変更/新公開面/秘密の境界変更など保護対象だけは明示承認なしに実行しない。他の通常開発と分離試験は継続する。GPT CHATからCodexへの追加起動は行っていない。

**完了条件**: Telegram送信・受信・ファイル送受信の全実経路で保護を実証し、VPN断でも自宅IPへfallbackせず、既存Gserverへ支障を出さず、性能測定・復旧・rollback証拠を残す。未検証をPASSにしない。

## 7. 2026-10-30 Master追補：Gserver VPN / ドメイン接続境界のみ

**本追補のスコープ**：Gserverに関わるVPN egress、受信用Domain/Ingress、Cloudflareアカウント間の所有権境界のみ。GateApp-Bot、Tumblr、SalesBot、UserBot各Projectの設計・実装・Currentは変更しない。参照した GateApp-Bot Issue #8 はドメイン区分の照合資料であり、他Projectへ追加実装を依頼するものではない。

### 確定した用途分離（メールアドレスは非掲載）

| Domain / zone | 用途 | 管理境界 |
| --- | --- | --- |
| `g-acebot.com` | 個人・会社・G-ACE系。Gserver共通基盤の候補 | A |
| `asterav8.jp` | Astera専用。Gserver一般用途の新規利用は禁止（個別承認時のみ例外） | B |
| `hentaigay.org` | Telegram／Tumblr専用。該当Gserver入口の候補 | C |

A/B/Cは論理的な所有・認証境界の識別子。**実CloudflareアカウントID、Zone ID、同一／別アカウント実態、DNS/Tunnel/Accessの配置・稼働状態は未実測**。異なる境界として設計し、接続・権限は実権限を照合してから変更する。管理メール、アカウントID、Token、Tunnel Secret、WireGuard鍵は公開GitHubへ記載しない。

### Gserver実装責務とドメイン可変化

- Gserverのサービス内に `asterav8.jp` 等のFQDN、Zone ID、Cloudflare Account ID、Tunnel ID、Webhook URLをハードコードしない。既存設定をいきなり消去・置換もしない。
- 各受信入口・サービスに `ingress_ref`（内部識別子）を設け、**サービス論理名 → 許可済みFQDN/Tunnel/認証プロファイル**を既存の設定/Secret管理層で解決する。例：`telegram_webhook_ingress` は採用した認証済み zone C のホスト名へ、`gserver_common_ingress` は採用した zone A のホスト名へ。これは設計上の識別子例であり新規API/DB/必須管理UIの追加指示ではない。
- Zone別にAccount/Zone/Token/Tunnel/Access Policyの権限とSecretを分離し、アカウント横断の万能Tokenを作らない。Gserver自身のサービスidentityとWebhook検証Secretも分離する。環境差分（dev/staging/production）に合わせて設定を切替可能にする。
- ドメインの変更は **設定マッピング＋DNS/Tunnel/Access＋Webhook callback登録** の一貫した変更単位として扱う。構造に依存しないよう接続面を抽象化するが、新しいドメインへ無承認に本番通信を送らない。
- 切替手順は現行経路read-only棚卸 → 新zoneの権限確認 → 変更前後のDNS/TLS/Tunnel/Webhook認証/オリジン非公開/送受信/rollback検証 → 明示承認済みの切替 → 実Runtime readback。両経路の並行運用も具体的に承認された期間/用途だけに限る。旧経路の自動削除なし。
- **Gserver VPNとの接続境界**：Windscribe日本通常/韓国予備の外向きBot通信はWireGuardの独立したEgressで保護。受信Webhook/TunnelとVPN出口は別責務。Ingress経路の応答やTunnel制御接続がVPN Kill Switchに遮断されたり、例外規則が直接WANの抜け道になったりしないことを実機で証明する。
- Telegram／Tumblr固有の業務機能・各Botの移行や構造変更は別オーナー。Gserver側は許可済みのホスト／API／Webhook契約を接続するだけ。TGserver、Vault、Webhook Gateway、DebugAI等の `g-acebot.com` への移行は未決定であり、今回行わない。

### Codex向け最小受入追加

1. `IN-DOM-01`: Gserverで利用するIngress/Endpointの現在のzone、Owner、認証、DNS/Tunnel参照を read-only で確認。値/機密は外部公開しない。
2. `IN-DOM-02`: Domain変更をアプリソースのFQDN書換え無しで設定だけで表現できること（mock/fake endpointによるオフラインテスト）。既存運用とBackward Compatibilityを維持。
3. `IN-DOM-03`: Domain/Zone A/B/CのToken交差使用、未許可zoneへの流用を拒否するテスト。
4. `IN-DOM-04`: VPN切断・日本韓国切替時、GserverのWebhook受信／応答とTunnel必要経路が維持され、保護対象BotのVPN外Egressが0件。具体的な許可最小化と実Hostのpacket/route観測で検証。
5. `IN-DOM-05`: 新Domainを実採用する場合だけ、DNS/TLS/Tunnel/Access/Webhookの登録・切替・復旧を実証。現時点は未承認・未設定・未実測。

**現在の実行状態**：GitHubへの設計引継ぎのみ。Cloudflare、Windows、WSL、Docker、Windscribe設定の変更、Codex新規起動、Runtime検証はいずれも実施していない。既存Gserver Current #9 と既存Codex主担当/Mutation Ownerを維持する。

## 8. 2026-10-30 防御層・Libral Vault連携の必須設計（Masterの訂正）

**訂正：従来の「VPN+Tunnel+Firewallだけ」の説明は保護範囲が不足。** 既存の自前暗号化・秘密情報管理の資産を含め、防御層ごとの目的・信頼境界・暗号化の有効範囲を明示する。今回の実装対象は**Gserver側の正式な利用口・設定・隔離・テスト**に限定し、共有Vault本体のSource・Runtime変更は無断で行わない。

### 現物Sourceの確認内容（Runtime稼働は未確認）

[Libral Vault README](https://github.com/seigo-gace/Libral-Vault/blob/main/README.md) に、単一Vaultモジュール、内部GPG部品、ACL/TTL、暗号化Secret保管、`useSecret` callback、暗号化Recovery Package、Key Rotation、署名/検証、Secretを返さずHTTP Providerへ投入する `POST /internal/v1/actions/http`、`/internal/v1/crypto/seal|unseal` 等の公式接続APIが記載される。**これらはSource記述であり、Gserverから到達可能か・接続済みか・使用許可があるかは未実測。** Vault内部GPGの直接操作・別Vault作成・Secret平文の外部配布は禁止。

### どの防御を、どこへ適用するか

| 防御層 | 防ぐ脅威・効果 | Gserver設計要件 |
|---|---|---|
| WireGuard | 自宅からの外向きトラフィックをVPN出口へ、経路上の通信を暗号化 | JP通常/KR予備、直接WAN fail closed、DNS/IPv6漏洩防止 |
| TLS/HTTPS | Telegram API、Cloudflare ingress、正規内部サービスとの通信内容を経路上から保護 | 正しい証明書/hostname検証、認証済みTLS。WireGuardをTLS代用にしない |
| Cloudflare Tunnel | 自宅への未許可のインターネット直接到達を減らす | Zone C/B/Aの所有権を保護し、Webhook真正性、origin遮断、callback先検証 |
| Libral Vault | Secretの保存時暗号化・ACL/TTL・認証付き利用と復旧 | Bot Token、Cloudflare Token、Webhook Secret等の利用箇所を棚卸し。**利用可能な正規APIだけ**で連携し、Provider SecretをBotへ返さない経路を優先 |
| Windows/WSL/Docker基盤 | アプリ突破時の権限横断・Host汚染 | 非root、capabilities制限、read-only rootfs、secret mount最小権限、network segmentation、更新/ログ/backup |
| 保存・バックアップ暗号化 | 記録/動画/DB/復元パッケージが流出した場合の読取り | データ分類（秘密/個人情報/媒体/公開）に応じた保存時・バックアップ時の暗号化、署名/改ざん検知、復元テスト。既存VaultのCrypto契約に適合する範囲を確認し、巨大メディアを無条件にVaultへ通して性能を壊さない |
| アプリ認証・入力検証 | Webhook偽装、SSRF、悪意あるメディア、リプレイ | Telegram secret_token、内部Service認証、ファイル形式/容量/リダイレクト制限、idempotency |
| 可観測性・復旧 | 防御停止の見逃し、誤設定固定、鍵漏洩後の被害拡大 | 通信出口観測、denyログ、Vault health/権限拒否監視、秘密のマスキング、Rotation/restoreの実証 |

### Vaultに関する設計時の必須の具体確認

1. **所在・Trust Boundary**：Vaultの実Host/インスタンス、正式API/MCP、Runtime到達性、認証手段、Consumer ACL、zone/Project権限をread-onlyで確認。既存VaultがContabo上にある場合は、**本件のContabo利用禁止**に従い、遠隔呼出し前提の実装をしない。接続できない場合はGserverの既存ローカルSecret管理で安全側に保護し、既存契約の下で利用可能な正規連携案を比較する。**勝手にVault本体を複製・専用化・移設しない。**
2. **守る対象**：WireGuard `PrivateKey`、Bot API Token、Webhook Secret、Cloudflare/Tunnel Credential、各種OAuth/DB/Backup鍵等を分類。どのSecretが誰の権限で、どの実行時に必要かと、起動・更新・復旧時にどこへ存在するかを図示する。
3. **秘密の使用方法**：Vaultに認められたConsumerなら正式 `useSecret` 相当または `actions/http` 経由を優先。利用側が平文Secretを永続保存しない。WireGuardのようにローカルコンポーネントへ秘密鍵を渡す必要がある場合は、既存ローカル機密管理と権限・メモリ・一時ファイル・起動順・プロセス再起動を明確にし、`actions/http` でWireGuard接続できると誤解しない。
4. **障害時挙動**：Vault不通／ACL拒否／鍵Rotation中に認証を無効化したり、平文env・公開ファイルへfallbackしたりしない。Botのキュー保存、停止範囲、復旧、鍵交換手順を定義。
5. **暗号化の範囲**：保存時暗号化と転送時暗号化、署名/改ざん検知、匿名化は別の要件。TLSとVPNとVaultを重ねても、Telegramへの提供データ、Cloudflareで終端するHTTPS、VPN事業者の出口以後の宛先メタデータ、アカウント関連性は隠蔽できない。曖昧に「完全暗号化・匿名」とは記述しない。
6. **過負荷/性能**：画像/動画すべてをVault APIで毎回暗号化することを既定にせず、既存データフロー・暗号化方式・容量制約を確認し、転送前後CPU/RAM/レイテンシ/アップロード時間を測定する。

### 防御評価の追加受入項目

- `CRYPTO-01`: 全SecretのOwner/保管先/消費主体/ログ露出を台帳化し、公開・平文残置・権限横断を拒否。
- `CRYPTO-02`: **利用可能と実証された**正式Vault連携があれば、ACL/TTL/Secret非返却/health/鍵Rotation中を実試験。利用不可なら`VAULT_RUNTIME_NOT_AVAILABLE`とし、採用する代替の境界と残リスクを明記。
- `CRYPTO-03`: 保存メディア/DB/Backupについて分類別の暗号化・復号権限・改ざん拒否・隔離Restoreを確認。
- `CRYPTO-04`: Vault障害とVPN障害の複合状態で平文/直WAN fallbackが無く、通常受信・キュー保持・復帰が安全であることを実測。
- `CRYPTO-05`: 単なる暗号ライブラリ導入やSource単体PASSではなく、Gserver実Runtimeの鍵使用・漏洩防止と、通信速度への影響を確認。

**決定境界**：この追補で既存のVault利用が正式契約上可能なら利用を検討するが、Vault提供元の改修、既存利用者のSecret移行、Contabo接続、新たな公開API/権限拡大は許可しない。必要な場合は影響範囲と承認事項を分けてMasterへ具体案を提示する。
