# VPN保護構成の実装・運用（2026-10-31）

設計正本は[レビュー済み引継ぎv3/R01〜R13](../handoffs/TELEGRAM_VPN_PRIVACY_2026-10-30.md)。Gserverは汎用Hostのまま、保護対象appの通信を隔離する。Contabo、既存Cloudflare/共有Vault/Gateway、Core/Storageは変更しない。

## 実装した範囲

`scripts/gserver_vpn.py` は秘密ファイルの検証、保護構成のprivate生成、独立VPN namespaceへのguard適用を先行する起動controller。WireGuard/暗号/Firewall自体を新しいVPN製品として再実装せず、digestを固定したGluetunと既存Linux nftablesを使用する。既存 `gserver_apps.py` のNET_ADMIN/netns共有禁止は緩めない。

JP/KRの原本は変更しない。WSL側のowner-only 0600コピーを使い、hooks/unknown項目/不正key/不正route/不正Endpointを拒否する。実設定のdual-stack/hostnameは受け入れ、初期runtimeはIPv4に限定した別0600設定へ変換する。hostnameの場合は明示的なpublic IPv4 pinが必須で、controllerがpublic DNS/DoHへ自動問い合わせすることはない。pinは接続先peer public keyの検証を代替せず、実handshake/出口IPを別途確認する。

生成bundleは既存directoryに上書きしない。Compose/guard/runtime設定のhashと原本hashを照合し、変化を検出したら起動を拒否する。bundleのruntime `wireguard.conf` は秘密そのものなのでGitへ入れない。新しいWG鍵/Provider Tokenを発行しない。デスクトップ原本・WSLコピーの自動削除/鍵ローテーションはしない。

## 起動順序と失敗時の処理

1. 全imageがローカルにあること、同名project/container/networkがないことを確認。pull/buildはしない。
2. VPN専用containerを待機entrypointで起動。まだWG/外部通信を開始しない。
3. container PIDと専用netnsを取得し、Host namespaceと同一なら拒否。短命sudo helperがnamespace FDを開きHost namespaceと異なることを照合し、そのFDを渡した `nsenter --net=/proc/self/fd/... nft -f guard.nft` で**そのnamespaceだけ**に適用する。非root controllerへroot PIDのnamespace読取権限を要求しない。
4. 物理eth0→選択WG endpoint UDPだけ許可。IPv4 tun0と限定loopback以外の出力はdrop、Docker DNS `127.0.0.11:53`もdrop。IPv6は当該namespaceだけ無効化する。HostのFirewall/daemon/DNSは変更しない。
5. PID/namespace inodeを再照合し、鍵をDocker stdinで専用tmpfsの0600ファイルへ供給してから起動markerを解放する。鍵をenv/argv/Compose本文に入れない。
6. VPN health後に独立guardのnamespace inode・rule fingerprintを再照合してからappを同一projectのVPN netns内で起動。appは非root、cap_drop ALL、read-only、追加network/portなし。DNSは非秘密inline configでVPN内resolverを指す。
7. 失敗したら今回作成したprojectだけstop。volume削除・他project操作・直接WANへのfallbackは行わない。既存projectへのadoptは拒否する。

VPN/app restartは現段階`no`。gatewayの再作成・JP/KR切替ではappも再作成する必要がある。controller中断やDocker/WSL再起動後にguard無しで勝手に外部通信を再開させない。自動復帰はguard再適用を含む実機試験後の追加段階。

## CLI

```text
python3 -B scripts/gserver_vpn.py verify jp /private/Windscribe-Tokyo-Shinkansen-WG.conf
python3 -B scripts/gserver_vpn.py verify kr /private/Windscribe-Seoul-Hangang-WG.conf
python3 -B scripts/gserver_vpn.py hints
python3 -B scripts/gserver_vpn.py preflight --vpn-image PINNED_GLUETUN_IMAGE --app-image PINNED_APP_IMAGE --cloudflared-image PINNED_CLOUDFLARED_IMAGE
python3 -B scripts/gserver_vpn.py render jp /private/Windscribe-Tokyo-Shinkansen-WG.conf --endpoint-ip VERIFIED_PUBLIC_IPV4 --vpn-image PINNED_GLUETUN_IMAGE --app-image PINNED_APP_IMAGE --cloudflared-image PINNED_CLOUDFLARED_IMAGE --output NEW_PRIVATE_DIRECTORY
python3 -B scripts/gserver_vpn.py start PRIVATE_BUNDLE_DIRECTORY
python3 -B scripts/gserver_connection_readiness.py --bundle PRIVATE_BUNDLE_DIRECTORY
python3 -B scripts/gserver_connection_readiness.py --local-status
python3 -B scripts/gserver_vpn.py set-endpoint-pin jp VERIFIED_PUBLIC_IPV4
python3 -B scripts/gserver_vpn.py pull-reference-images --confirm-registry-pull
python3 -B scripts/smoke_gserver_vpn_live.py
```

上記は引数契約の説明であり、placeholderのまま実行する手順ではない。通常userから起動し、必要なDocker/nsenterだけ既存sudo権限を使う。生成親directoryは既存のowner-onlyローカルstateを選ぶ。real image digest/endpoint pin/実app契約がない状態で適当な値を埋めて稼働させない。

## 未実装・未受入を明確にする

- controller/Compose解析/単体試験は**実WireGuard接続・kernel漏洩防止の証明ではない**。NET_ADMIN、nftables kernel適用、Gluetun digest/起動権限、MTU、DNS、IPv6、kill/recreate時の漏洩を隔離実機で試験する。
- `render --cloudflared-image` で **cloudflared を `network_mode: service:vpn` として同じguard付きnamespaceへ追加**できる。Tunnel tokenはCompose/envに入れず、bundle内の0600 `cloudflared.credential` を `start` 時にcontainer tmpfsへstdin供給する。Cloudflare zone/Tunnel/Access/WAF/Webhookの**実変更・実接続は行わない**。**Cloudflare IP秘匿の達成とはしない。**
- appの設定/Secret/永続データ/healthcheck/正当な宛先はapp Owner契約から追加する。新Botを生成したり既存BotのSourceを書き換えたりしない。
- guardは出口経路の防御。Telegram API宛の不正持出し、webhook replay、SSRF、媒体処理制約はapp契約と攻撃試験も必要。namespace内IPv4を許すことを全攻撃防止と呼ばない。
- endpoint pinは現在の有効性/出所を記録し、更新時は新しいbundleを生成して再試験する。endpoint名の自動DNS解決、JP/KR自動切替は未実装。
- Vault正式利用とSecret暗号化・rotation・復元は未実証。既存private-file保護を維持し、別Vaultで代替しない。
- Baseline/JP/KR/媒体/p50/p95/p99/失敗率/CPU/RAM/IOと必要閾値が揃うまでPERFORMANCEはNOT_VERIFIED。速度未達や漏洩を保護解除で回避しない。

## 電源断からの復帰と従来の起動失敗

`bash scripts/verify_gserver_resume.sh` は重点テスト→同一端末sudo本人認証→read-only Core/Owner Storage/SQLite quick_check→既存2app probeの順。修復/再起動/設定変更をしない。Core/Storageの実readbackは既存container内で行い、Tokenを外へ出さない。SQLiteはmode=ro/query_onlyで照合し、spoolをclaimしない。

Windows→WSLの自動起動と、現在のCore応答/DB整合性を別判定する。電源断前のdata fingerprint/backupがなければ全データ一致PASSにしない。既存app probeの失敗は分類したDocker理由・合成process例外・exit/OOMをcleanup前に出す。生の実appログ、認証情報、環境変数は出力しない。

## 次の実kernel受入（VPN接続より前）

`scripts/smoke_gserver_vpn_guard.py` は、既存Coreのlocal imageを新規random projectで使い、**同一Compose bridge上のprivate peer canary**（RFC1918、WAN/public宛なし）でguardを実証する。Host bridge gatewayへのbindはWSL/Docker差で不安定なため使わない。VPN設定/鍵は使わず、WG接続・public宛送信・Cloudflare変更・image build/pullはしない。guard適用前にpeer canary到達、適用後にloopback成功/peer遮断/nft drop counter増加を確認する。成功でもWireGuard/実kill-switch/JP-KR/DNS/IPv6/性能の全受入とはしない。

controllerはCore/Owner Storage応答・既存containerを前後照合し、新規probeと専用network・Host listenerを必ずcleanupする。guardは対象netnsのみ、Host table/daemon設定は変更しない。helper失敗時は安全なreasonと秘匿化したnftエラーを出し、ログ未生成を原因不明のまま見落とさない。実機実行には同じ端末のsudo本人認証が必要。kernelのmock試験は実機PASSではない。

Gluetun公式Sourceはrepository IDを維持して `passteque/gluetun` へ移行済み、公式READMEでimage名は従来どおりと確認。2026-10-31の公式latest release読取はv3.41.3。これは候補情報でありdigest監査・取得・PC適用の証拠ではない。

**2026-10-31 PC実機:** Master端末で `smoke_gserver_vpn_guard.py` が VERIFY=PASS（peer canary・namespace nft guard・Core不変）。WireGuard実接続・出口IP・DNS/IPv6・性能・cloudflared同一経路は未受入。

## 実WireGuard出口受入（2026-10-31 Codex R15）

`scripts/verify_vpn_live_host.sh` は重点テスト→同一端末sudo本人認証→秘密を出さないreadiness→`smoke_gserver_vpn_live.py`を実行する。JPのみの受入にはKR pinを要求しない。両profileはowner-only 0600、bundle0700、非秘密app DNSファイル0644を維持する。既存Coreの停止・再配置、image pull/build、Host Firewall変更は行わない。試験専用projectだけ起動・停止・cleanupし、Core/Storage/既存containerを前後照合する。

Gluetun loopback APIはアプリhealthにだけ使用し、外向き通信・Kill Switchの受入根拠にしない。R15の実測は次の範囲を対象とする。

- UID65534 appから固定public IPv4 HTTPSと名前付きHTTPSを実行。標準TLS検証、環境Proxy無効、redirect拒否、本文サイズ制限を適用する。出口public IPv4・JP/KR地域一致を検査し、IP本文は表示しない。診断先はCloudflareの公式`/cdn-cgi/trace`であり、所有zone/Tunnel/Accessの操作ではない。
- `wg show tun0 latest-handshakes` / `transfer` のみを非表示で読取。直近handshakeと試験前後の受信・送信量増加を確認する。秘密が出る`dump`/`showconf`は使用しない。
- Docker組込DNSへのUDP/TCP試験送信が、それぞれ独立nft drop counterへ計上されることを確認する。namespace IPv6無効化とpublic IPv6宛TCP遮断を確認する。閉じたloopback portをIPv6遮断の根拠にしない。
- 同じappからpublic IPv4 TCP到達が成功することを確認してからVPNを停止し、同じ宛先の遮断を再試験する。appが動いていること・同一namespace/guard不変も照合する。Docker exec失敗・不正なJSON・不明な試験状態はFAIL。

```bash
GSERVER_VPN_REGION=jp GSERVER_CLOUDFLARED_CREDENTIAL= bash "$HOME/Project/Gserver/repository/scripts/verify_vpn_live_host.sh"
```

これは**実機で実行して成功した範囲だけ**が受入となる。少数HTTPSの応答時間は性能目標の合否判定ではない。DNS全経路・Proxy/SSRF・実媒体・切替/再接続・速度/安定性・復元・F01〜F08の総合受入は別途必要。

Cloudflare ingressは別Gate。以前の任意credential投入では本番Tunnelへ試験replicaが参加し得るため、この出口試験ではcredential指定を拒否する。所有zone、既存契約、隔離Tunnel、Access拒否/許可、connector DNS/起動方式を確認してから統合する。既存rendererのcloudflared scaffoldは実稼働受入済みではない。既存Cloudflareを変更せず、Asteraゾーンを流用しない。

Gluetun v3.41.3は起動時に`/etc/passwd`へ書くためVPNサービスだけread_onlyを解除している。app/cloudflaredのread_only、capability制限、guardは維持。appはCore imageをPython実行体として再利用し、Coreのhealthcheck/Workerは起動しない。DNS Configは`app-resolv.conf`をfile方式で適用し、UID65534で実読取を検査する。失敗時はcleanup前のState/Health/秘匿診断を取得する。

公式根拠: [Cloudflare /cdn-cgi endpoint](https://developers.cloudflare.com/fundamentals/reference/cdn-cgi-endpoint/)、[WireGuard tools wg manual](https://git.zx2c4.com/wireguard-tools/tree/src/man/wg.8)。
