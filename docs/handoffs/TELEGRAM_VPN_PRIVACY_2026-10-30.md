# Gserver Telegram送受信通信保護｜Codex向け統合設計・厳格監査 v2
**更新:** 2026-10-30 JST ｜ **STATUS:** DESIGN_AUDITED / SOURCE_READBACK_CONFIRMED / RUNTIME_NOT_VERIFIED / NOT_DEPLOYED
**管理:** [Gserver Current Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9)・[現行設計](https://github.com/seigo-gace/G-ACEserver/blob/main/docs/architecture/OVERVIEW.md)・F01–F08（46既存Task維持）。別Stage・別Projectは作らない。これは**Gserver側だけの接続・保護設計**であり、GateApp-Bot/Tumblr/SalesBot/UserBotのソース、共有Vault/Gateway/TGserver、Contaboの変更を委任しない。既存Codex Ownerと作業境界を尊重する。

## 0. 本文の位置付けと優先順位
このv2は同一ファイルの以前の追補1〜9を整理統合した**現行引継ぎ正本**。過去の訂正と旧記述はGit commit履歴に残す。Sourceで観測した事実、Master確定要件、設計提案、未検証を混同しない。Masterの「自宅IPの露出低減・送受信保護・速度劣化を許容しない・既存Cloudflare/Vault防御を削らない・無駄な二重機能を作らない」を中心の受入目標とする。

### Master確定の入力
- Windscribe Build A Plan：日本 **Tokyo - Shinkansen** を通常、韓国 **Seoul - Hangang** を予備、無制限通信。
- 生成済みとMasterが報告したローカル設定ファイル：`Windscribe-Tokyo-Shinkansen-WG.conf` と `Windscribe-Seoul-Hangang-WG.conf`。**ファイル内容・保存場所・契約状態・実接続は未確認**。秘密鍵はGitHub、チャット、CI、ログに出さない。
- Windows 11 / WSL Ubuntu / Docker/Compose上の既存Gserverのみ。Windowsの通常通信やLAN、F/Gデータ、既存Serviceを不用意に変えない。Contaboは今回使用禁止。
- Domain用途：`g-acebot.com`＝G-ACE一般(A)、`asterav8.jp`＝Astera専用(B)、`hentaigay.org`＝Telegram/Tumblr専用(C)。A/B/Cは所有権・認証上の**論理境界**。実CloudflareのAccount/Zoneの同一性・設定は未実測。管理メール／Account ID／Secretを公開Repoへ記載しない。Astera zoneのGserver新利用は個別事前承認なしに禁止。
- VPNがあるためCloudflareのTLS、WAF、Rate Limit、DDoS対策、Access、Tunnel、Origin非公開、Webhook認証を外したり弱めたりしない。Cloudflareに**現時点でそれら全機能が有効と主張しない**。

## 1. 厳格Source監査：2026-10-30実際に読んだもの
| Source（owner repo main） | SHA（blob） | 直接確認した事実 | 未実証事項 |
|---|---|---|---|
| `deploy/compose.gserver.yaml` | `d8f3c4af6239c06108aada484eb3cceb2f114467` | `network_mode: none`, `read_only: true`, `user:65534`, `cap_drop:ALL`, `no-new-privileges`, pids64, memory256MiB, CPU0.5 | 現在PCで適用された実Compose/Runtime |
| `scripts/gserverctl.py` | `b47daec99f617e1ccf65fdd75b507a020208e5f2` | `enable-local`系でネットワーク遮断をloopback公開`127.0.0.1:18765:8765`＋Docker bridge `gserver-local-v2`へ**切り替える** | bridge外向き通信が実際どこまで許可されているか、実ネットワークACL |
| `app/tgs_bridge.py` | `f695223617334e7ca2742fcdade52c06a8568671` | 認証済み内部GatewayへHTTPS送信するSpool Worker (`urllib`)、retry/idempotency等 | 通信先IP/Cloudflare/TLSの実経路とVPN固定 |
| `docs/architecture/BOT_TGS_BRIDGE.md` | `351fdf8eb1f9937c7667a107b3a02c3dbb2b05fc` | Gserverの現行Bot機能は**運用イベント受付→SQLite→既存Gateway→TGserver**が中心。メッセージ本文・chat/user ID・メディアは保存せず、Telegram Bot本体を新設しない | Telegram Bot本人の現在のWebhook/Polling・メディアの全経路 |
| `docs/requirements/FINAL_ACCEPTANCE.md` | `a7439fdb2b319cbb7245910ee1f640cdbc01dee8` | F02/F06/F07/F08の既存安全性・CLI・復旧条件、機密と既存Sourceを保護 | VPN/今回の個別機能のRuntime受入 |
| [Libral Vault README](https://github.com/seigo-gace/Libral-Vault/blob/main/README.md) | GitHub Source確認 | 単一Vault、暗号化Secret、ACL/TTL、署名、鍵Rotation、暗号化Recovery、正式Module/API | Gserverからの許可された接続・配置・生存確認 |
| DebugAI branch `test/telegram-egress-isolation-20261030` | `tests/test_telegram_egress_isolation.py` blob `514f1434d9ab53b3a3adce538eebdebfe791cd2a`; `tests/test_telegram_socks5_socket_probe.py` blob `22c4c5fccb396dd1089c2a999046ebead15210a0` | 模擬8テスト・loopback5テストの**ソース存在**を読戻し。後者には`test_direct_path_remains_without_firewall`が明記 | 今回の再実行、HostのFirewall、WireGuard漏洩試験。過去「8/8・5/5 PASS」は履歴報告に留める |

**重大な発見 A:** `127.0.0.1`への受信公開は外向きEgressを遮断しない。現行のbridge profileが既定の外向き経路を持つ可能性があるので、VPNを追加するだけでは漏洩保証がない。**Gserver本体の既存安全プロファイルを無断で全面置換せず、Bot等の保護対象ごとに境界を実装する。**
**重大な発見 B:** 現在のGserver内部イベントBridgeと、将来接続するTelegram Bot runtimeを同一視しない。Bot群の所有Repo移設・統廃合は別作業。Bridgeから既存共有Gatewayへの必要通信は、正規の契約とCloudflare zone所有権に従う。
**重大な発見 C:** VaultのSource機能をGserver利用中と捏造しない。VaultがContaboにある場合、この案件からそこへ新接続しない。正式な利用口と認証が整うまでは既存GserverローカルSecret保護を維持し、秘密の平文公開・別Vault設置で穴埋めしない。

## 2. 何が誰に見えるか（秘匿性の正しい境界）
1. **Bot→Telegram Bot API/ファイル取得/外部API**：保護対象EgressをWireGuardへ固定すれば、Telegram等には通常Windscribe出口IPが見える。自宅のISPはWindscribeへの接続を観測し得る。TelegramのBot ID、アカウント、投稿内容、媒体自体をVPNで匿名化できない。
2. **Telegram→Cloudflare→Gserver Webhook**：TelegramはCloudflareの公開URLへHTTPS送信。これはWindscribeを通らない。CloudflareはTLS終端などの設定次第でデータにアクセスし得る。Tunnelは自宅公開ポートの代替であり、Webhook正当性は別に検証する。
3. **Gserver `cloudflared`→Cloudflare**：これは別の外向き接続。**Windscribeへ通すかどうかは未確定**。直結ならCloudflareから自宅回線の送信元IPが見える可能性がある。「Cloudflareへ届く前もVPNで隠す」要件を勝手に完了としない。Tunnel通信をVPN隔離空間へ通せるか、死活・応答・遅延・再接続を実機検証して判断。通せない場合は残リスク／性能差／必要な明示判断を提示。既存Tunnelを壊さず、BotだけVPNを通す案を自宅IP完全秘匿と誤称しない。
4. **Cloudflare/Tunnel/受信とVPN/送信の相互作用**：各経路を別Service identityと最小ACLで結ぶ。受信経路維持のためにBot全体の直接WAN許可を開かない。
5. **ドメイン切替**：ソースにFQDNやZone IDを固定しない。既存設定管理を使ってサービス論理名→許可済みzoneのFQDN/Tunnel/認証設定を解決する。DNS/Tunnel/Access/Webhook callbackの切替は独立の**保護操作**、Masterの個別承認後のみLive変更。新規UI、データベース、Routerを作るための要件ではない。

## 3. 採用候補の最小アーキテクチャとネットワーク境界
- **Ingress**：既存契約に適合するCloudflare Tunnel/HTTPS入口を確認し、正規WebhookをTLS・アプリ認証・限定受信で処理。管理用入口はAccess認証を維持。Telegram自身は一般的な対話AccessログインやCloudflare Service Tokenを自動送信できないため、Webhook入口は**別の最小公開エンドポイント**とTelegram `secret_token` とアプリ検証を組み合わせる。CloudflareのWAF/Rate LimitはWeb API向けの**block/limit**を検証し、ブラウザ専用challengeをTelegramへ一律適用しない。Provider送信元IPだけを本人確認の唯一の根拠にしない。
- **Outbound**：保護対象Botとメディア送受信、対象外部APIだけ、独立したVPN egress専用netns/ゲートウェイでWindscribe JP通常／KR予備。DNS・IPv4・IPv6の直接経路をネットワーク層で閉じる。Botアプリがproxyを無視して直接socketを開いてもWANへ出られない構造にする。新Gatewayが本当に不要なら二重Proxyは作らない。共有`network_mode: service:...`は候補だが、Ingress/内部アクセスと競合するなら適切な別方式を選ぶ。
- **Firewall/Kill Switch**：プロセス起動前からdefault-deny、VPNトンネル/経路/handshakeとWAN出口を照合。**Windscribeの公式WindowsアプリFirewallは手動WSL WireGuardには自動適用されない**。Gserverの専用netns/必要なHost境界で独立した防御が必要。Dockerの`iptables`/`nftables` backendと`DOCKER-USER`等の適用場所を実機確認し、`ufw`のみ/設定ファイルだけで満足しない。既存Host firewallやDocker daemon全体を無断変更しない。VPNの接続先例外は最小限、VPN endpointやDNSのIP変更・悪用・IPv6ルートの抜け穴も確認する。
- **起動停止**：Firewall ready→WG ready→出口IP/route確認→Bot online。切断・handshake停止・再起動・切替ではfail-closed、直接fallbackなし。両国障害なら未処理キュー保持と外向き停止。切替過敏を防ぐcooldown/hysteresis、勝手な自宅回線への切戻し禁止。ゲートウェイの機能停止が既存GserverのローカルAPI/Storageを巻き込まないこと。
- **内部LAN/DB/Storage**：VPN経由にする必要のないローカル通信は私有ネットワークの最小許可で維持。広い`192.168.0.0/16`や`host`全許可は避ける。VPN例外からWANへ踏み台接続できないことを確認。
- **Vault/保存暗号化**：既存Libral Vaultの公開契約が安全に使えるなら、Secret ACL/TTL/署名/暗号化保存を利用。GPG内部への直接接続、新Vault、秘匿値コピーは不可。WG PrivateKeyはVPNプロセスにローカルで必要であり、VaultのHTTPプロキシでWG通信を代替できない。Vaultの存在可否が不明の間は現行の厳格な権限付きローカルSecretを保護し、平文env/logへfallbackしない。媒体/DB/Backupはデータ分類に従い必要な保存時暗号化/完全性検証を追加するが、大容量動画をVaultへ全量通す二重暗号化を既定化しない。
- **Cloudflare維持**：現行DNS/TLS/HTTPS強制/WAF/Rate Limit/DDoS/Access/Tunnel/Origin隔離の実有効設定を読取専用で採取。**VPNを理由に削除・弱体化・置換しない**。既存Astera zone Bを別製品に使わず、Zone CのTelegram/Tumblr専用設計とZone AのG-ACE基盤を分離。共有Webhook Gateway/Vault/TGserverの提供元Source/Runtime/鍵には無断変更しない。

## 4. 攻撃前の予防と、攻撃時の対抗策（必要な防御だけ）
| 攻撃/故障 | 予防策（事前） | 発生時の対抗・復旧 |
|---|---|---|
| VPN断・経路逸脱・DNS/IPv6漏洩 | netns/Firewall default deny、IPv4/6・DNS/DoH/Proxyの経路検証 | 漏洩試行を遮断、Bot Egress停止、出口IPとFirewall照合後復旧 |
| Webhook偽装・replay・多量Update | HTTPS、Telegram header secret、正確なroute/method/body制限、`update_id`冪等性、rate limit | 401/403/429/413相当の適切な拒否と監視。正規配信を止めず、必要なら限定隔離。Telegramのretry/ACK仕様に合わせてdurable受入後のみ成功応答 |
| DDoS/大量リクエスト | 既存Cloudflare WAF/DDoS/rate limit、アプリの同時実行/Queue上限 | Cloudflare側の対象入口限定防御、処理過負荷の閉塞、再送増幅と無限ループ防止。challengeの一律適用は禁止 |
| Bot Token/Cloudflare Token/鍵漏洩 | Vault/ローカルSecret権限、zone別Token最小化、アクセスログの秘匿 | 該当Credentialの失効・再発行、アクセス範囲隔離、影響確認、秘密の入替え、監査イベントを秘密なしで記録 |
| 悪意ある外部URL・SSRF・DNS rebinding | 宛先契約、URL scheme/hostname/IP解決の二重検査、redirect先の再検査、local/metadata宛拒否、外向き宛先最小化 | 外向き遮断、該当ジョブ隔離、悪性ファイル・リダイレクト記録の安全な分析。VPN出口経由でも内部資源へアクセスできてはならない |
| 危険な画像/動画・Zip爆弾・容量攻撃 | サイズ/時間/stream上限、非root隔離、保存先制約、MIME/実形式検証、bounded Queue | 処理中止、隔離・削除は安全な既存手順、他Bot/共有Volumeを保護。メディアを無条件に二重暗号化・全量コピーしない |
| コンテナ侵害・横移動/情報持出し | cap drop、非root、no-new-privileges、書込み領域最小、ACL、Docker socket非公開、Egress宛先制御。**正規Telegram API宛の不正送信**はネットワーク宛先許可だけでは防げないため、Bot所有側の承認された送信先/chat・機能権限・送信回数上限・内容検証を接続契約で確認 | 対象Serviceだけ隔離、Secret無効化、改ざん/ログ確認、既知良品のimmutable image復元。**VPNは攻撃者の外向き持出しを防ぐ仕組みではない** |
| Volume/DB/バックアップ破損・暗号化攻撃 | 保存時暗号化、改ざん検知、最小権限、永続Volume保護、復旧用コピーの隔離 | Queue・Current・データ整合確認、暗号化Backupの隔離復元、必要な資格情報の交換。既存F/G原本を消さない |
| サプライチェーン更新・設定事故 | 既存immutable image/pinned dependencies、差分・CI・制限権限・rollback | 変更停止、直前revision/構成へ安全にrollback、Source/Runtime/Evidenceを照合 |
| Vault/Cloudflare/Windscribe同時障害 | 機能を単一新依存に不必要に集約しない。Provider/Secretのfallbackで保護を外さない | 発生した経路だけ停止/キュー保持。Cloudflare/Gateway側は正式Ownerへ通知、他Projectを独断で再起動しない |

**運用最小手順**：検知→影響範囲を限定→危険な経路/Tokenだけ遮断→秘密なしで証拠確保→正式契約で回復→正常経路・外向きIP・Webhook・Queueを読戻し。自動攻撃反撃/相手への攻撃/新IPSを既定で導入しない。OS/Containerの最小限の更新・安全なPatchは既存Gserver運用範囲で管理。

## 5. 「速度を絶対落とすな」の技術的受入基準
**方針は「速度を落としてもよい」ではない。** ただし暗号化/経由地追加の物理コストを未測定のまま「ゼロ遅延」と保証するのは誤り。**実測で性能条件が未達なら製品適用を不合格にし、原因を修正する。安全防御を外した直接通信へfallbackして速度だけPASSにしない。**

- **比較経路**：現行Gserverローカル処理（非変更baseline）、独立した管理下の速度計測先での制御された非VPN baseline、JP VPN、KR VPN。自宅IPをTelegramへ直接晒す無承認の実Botテストをbaselineのために行わない。
- **測定**：p50/p95/p99 API往復、Webhook受信→durable ACK、Bot処理待機、テキスト・小/大メディア送受信のthroughput、成功率、UDP packet loss/retransmit、CPU/RAM/IO、MTU/断続接続、VPN切替・復旧時間。Cold/warm・同一サイズ/回数・時間帯/CPU負荷の条件を記録し、複数サンプルで比較する。
- **合格境界**：保護対象外のLAN/WSL/Storage/既存APIの**性能退行なし**、保護対象のアプリ応答・必要throughputが**Masterの要求水準を満たすこと**を測定で証明。計測誤差内の差と実質的劣化を区別し、具体的な閾値は実baselineを観測して根拠付きで決定。規定がないまま固定%を捏造しない。安全性が満たせても性能未達なら`PERFORMANCE_GATE=FAIL`、未測定なら`NOT_VERIFIED`。
- **合理的な最適化順**：最短・低遅延なJP/KR出口選択→不要なVPN中継/Proxy/暗号化コピー排除→LANはローカルのまま→既存Queue/Connection reuse/keepalive→実測MTU・並行数調整→リソース上限最適化。WAF/認証/Vault/TLS/Kill Switchを解除して速度を稼がない。KR切替が改善するかも必ず実測。
- **容量・コスト**：C/D/WSL 既存場所、Docker memory/CPU制限を実測して増分だけ採用。追加月額プラン・別VPN/Server/有料WAF/監視を勝手に導入しない。

## 6. 簡素化：何を追加しないか
- 既存Libral Vaultの複製、別GPGサービス、別Cloudflare Gateway/Tunnelの勝手な生成、別Telegram Bot runtime、新MCP・新AI監視・新ダッシュボード。
- Tor/多段VPN/不要な二重Proxy/巨大動画の一律再暗号化/Windows PC全体のVPN化。
- 「WAFがあるからWebhook secret不要」「VPNがあるからTLS/Cloudflare不要」「VaultがあるからFirewall不要」など機能削減。
- Docker daemon 全体、Hostネットワーク、家族LAN、共有サービス提供元、Astera zone の無断変更。
- Browser challengeをTelegram webhookに広くかける、Webhook入口を一般Cloudflare Access bypassで広く無認証化する、SecretをURLやログに埋め込む。

## 7. Codex実行順と実測の受入データ
**Codexの既存Gserver Current/CU/Mutation Ownerが優先**。GitHub Issue #9の既存F02/F06/F07/F08に紐付く設計差分であり、今回ChatがCodexを起動したことを意味しない。

1. **read-only Current/Source/実Host確認**：Branch、実Docker Compose profile、WSL/DNS/IPv6/route、Bot runtimeの実Owner・Webhook or polling、Vault正規接続、Cloudflare zone A/B/Cの許可範囲・WAF/Access/Tunnel設定。現行ステータスを推測しない。秘密や家庭IPを公開しない。
2. **通信フローと秘密の完全棚卸**：Bot API send、getUpdates、Webhook、getFile、メディア取得/アップロード、一般外部URL、Gateway/TGserver、LAN/DB/Storage、cloudflared制御、Provider token。各通信にOwner、DNS、source/netns、宛先、認証、出口、fail mode、性能制約を記録。
3. **最小設計選定**：現行`none`→`loopback bridge`の安全境界を壊さず、Bot egressだけのVPN隔離方式とTunnel入口を設計。CloudflareへVPN出口を使うかはIP秘匿目標・安定性の比較と既存権限で確定。既存Vaultは正規接続の実行可否を別判定。
4. **隔離実装→構成/静的/正負テスト**：FirewallをBot開始前に有効化、WG JP/KR、DNS/IPv6、Ingress ACL、Webhook認証、ルーティング、最小権限。共有Service提供元を変更しない。
5. **実Host破壊試験（安全な隔離環境）**：VPN kill, DNS failure, IPv6 direct, proxy bypass, Docker/WSL restart, Tunnel/Webhook攻撃模擬, Vault障害, credential rotation, Queue overflow, bad file/URL, data restore。正規Webhookも維持されること。
6. **性能最適化・回帰・適用判断**：baseline vs JP/KR、LAN退行、E2E、CF/WAF既存ポリシー退行、Rollbackを複数回比較し、全受入合格まで本番保護済みとは呼ばない。
7. **証拠保存**：既存Issue #9 / `docs/CURRENT.md` へ正確なSource/CI/Host/Runtimeの結果、sha、試験範囲・日時、fail理由・残リスク・Rollbackを最小重複で記録。既存Codex作業を止めない、外部AI起動やPR AIレビューなし。

### 受入ゲート（いずれも現時点NOT_VERIFIED）
| Gate | Pass条件 |
|---|---|
| `FLOW` | 実Bot別に送受信/Webhook/Polling/getFile/外部依存を全数追跡、保護外経路が0 |
| `IP` | 実VPN出口JP/KRを確認、Telegram関連外向き直WAN0、cloudflaredの実出口とCloudflareから見えるIPの扱いも明記 |
| `NET` | Docker`none`/bridge差分、Host転送・Docker Firewallの実適用、IPv4/IPv6/DNS/DoH/Proxy/UDP別NIC経路を試験、漏洩0 |
| `INGRESS` | 正規Webhook/Polling成功、偽Token/偽造/過大入力/replay/攻撃rate拒否、WAF/TLS/Access/Tunnel/Originの既存防御は削減0 |
| `CRYPTO` | Vault接続の実状/正式権限、Secret保存・ACL、Key rotation障害、媒体/Backup暗号化・復旧、ログ非漏洩の証拠 |
| `RESPONSE` | VPN停止、認証漏洩、SSRF、悪性媒体、Service侵害、DDoS、更新事故を隔離・復旧・再検証 |
| `PERFORMANCE` | 必要な転送速度と応答時間を統計付きで実証し、既存ローカルサービスに退行なし。未達はFAIL、未測定はNOT_VERIFIED |
| `OPS` | 既存F/G/Volume/Spoolと業務保持、Docker/WSL再起動、ドメイン変更の設定分離、復旧・Rollback、他Projectへの影響0 |

**検証事実の境界**：2026-10-30の本監査はGitHub Source/設計と外部公式仕様照合であり、Cloudflareアカウント画面、PC Host packet、Windscribe Runtime、Vault接続、実Bot E2Eはアクセス・実証していない。万全・秘匿済み・性能維持達成とは言えない。

## 8. 公式技術根拠（適用時に再確認）
- Telegram Bot API（Webhook secret/getFile/getUpdates/再送）：https://core.telegram.org/bots/api
- Cloudflare Tunnel / outbound-only / origin：https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
- Cloudflare Tunnel Firewall/7844：https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/
- Cloudflare Access webhook path policy: https://developers.cloudflare.com/cloudflare-one/access-controls/policies/common-policies/
- Cloudflare WAF Rate Limiting：https://developers.cloudflare.com/waf/rate-limiting-rules/best-practices/
- Docker Compose networking/service mode：https://docs.docker.com/compose/how-tos/networking/
- Docker Firewall/ufw/DOCKER-USER：https://docs.docker.com/engine/network/packet-filtering-firewalls/
- Windscribe FirewallはWindows desktopアプリ専用設定：https://windscribe.com/knowledge-base/articles/firewall-modes

**END.**