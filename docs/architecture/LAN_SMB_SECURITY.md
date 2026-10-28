# 家庭用回線 / Gserver のLANファイル共有セキュリティゲート

## 目的と承認境界
Master Windows 11 の \`G:\GserverStorage\files\` だけを、妻 Windows 10 から同じ宅内LANで動画転送できるようにする。既存Docker Gserver \`127.0.0.1:18765\` と旧8765、G:/F:の既存原本、GitHub開発面には手を加えない。本書の設計・read-only監査は**共有の公開許可や設定変更ではない**。個々の作業は実Hostで現在値を確認し、既存への影響・即時ロールバックを満たすまで停止する。

## 脅威と通信方式
- 自宅回線でも、マルウェア感染端末・古いWindows・偽のWi-Fi接続・ルーター設定不備・共有資格情報の漏えいが脅威。回線種別が家庭用であることは暗号化やアクセス制限の代替ではない。
- **同一宅内**: 別のHTTPプロキシ/リバースプロキシを立てず Windows標準 SMB 3.x (SMB2/3 family) を利用。新規共有では共有単位でSMB encryption（\`New-SmbShare -EncryptData $true\`）を有効化し、SMB signingを要求。SMB1とゲスト/匿名ログオンは使用せず、有効化しない。SMB署名・暗号化の実有効性は接続成功時に readback。クライアントWindows 10とWindows 11双方の実バージョン/対応を確認する。SMB署名と暗号化は機能が異なる。暗号化された接続ではSMB signingヘッダが省略される場合もあり、暗号化が完全性保護を含む（https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/reduced-performance-after-smb-encryption-signing）。実通信の negotiated dialect と暗号化有無で判断し、署名欄の値だけで安全性を誤判定しない。
- **宅外**: ルーターでTCP445/NetBIOS 137–139/管理HTTPポートを転送しない。WAN公開、DDNS+SMB直接公開、DMZは不可。将来の宅外アクセスには、明示許可後の WireGuard 等のVPNを別ゲートで検討。家庭内LAN転送だけならVPN/プロキシは必須ではない。UPnP/ルーターの既存設定は読取・影響分析なしに変更しない。
- Wi-FiはWPA2-AESまたはWPA3を使用、WPSを極力無効化し、家庭内の信頼端末とゲスト/IoT端末を分離する。ゲストWi-Fiに妻PCがつながるとLAN共有不可の場合がある。
- **公開する範囲**: \`G:\GserverStorage\files\` だけ。専用の非管理者ローカルアカウントにshareとNTFSの必要な権限を付与。Everyone/Guest/匿名の書込みを禁止。親 \`G:\` や他share・一般Usersグループの権限を無造作に削除しない。Gserver WSLの既存書込み・Docker読取りの権限維持を回帰確認する。
- Windows Defender Firewallは Private profile の**妻PCの確認済みLANアドレス**だけからTCP445受信許可。IPがDHCPで変化する場合はルーターDHCP予約を検討し、未確認サブネット全体への拡大は避ける。Public/Domain profile、WANからの受信許可や全ルール一括有効化は禁止。
- **妻PC更新**: 一般Windows 10は2025-10-14通常サポート終了。2026-10-28時点のMicrosoft案内では、対象Windows10でConsumer ESU登録により2027-10-12までの保護が可能。実PCでエディション、更新適用とESU加入状態を確認する。未保護/古いOSからの書込み共有開始はゲート保留。Windows11へ移行できるなら優先。
- 4TB級転送は回線帯域よりWi-Fi品質、HDD書込み、CPU暗号化負荷の影響が大きい。初回小容量ファイル→内容SHA256照合→数GB→中断再開/空き容量/実測速度へ段階的に進める。大量ファイル一括コピーはコピー元を削除せず、転送中断時の途中ファイルを「完了」と扱わない。バックアップ/復元がない状態で移動（切り取り）を推奨しない。

## 共有設定前の必須ゲート
1. **Master PC**: 既存Private profile/SMB service/445 listen/共有名空きは実機PASS。ただしSMB1機能の状態・署名の必須化・SMB暗号化対応・既存NTFSの広範Write ACE・Firewallルール適用範囲は未検証。registry \`SMB1/SMB2=UNSET\` は機能状態の確認ではない。
2. **妻PC**: 同じ信頼できるLANに接続し、Windows10 build/更新とESU有効性・IP・SMB2/3対応・他のネットワークプロファイルをread-onlyで確認。本人が貼るログはローカルIP/ユーザー名/資格情報を不要に含めない。
3. **共有有効化**: 管理者権限での新規専用User作成/強固なパスワード生成は秘密をチャットやGitHubに書かずHostに保存。固有の \`GserverTransfer\` 共有を \`EncryptData\` と専用Principal限定で作成。NTFS ACLとFirewallの追加部分のみを事前記録し、元の設定に戻す操作を同時に用意する。リモート範囲未確認なら共有を有効化しない。Windows Defender・既存共有/サーバープロセスは止めない。
4. **受入**: 妻PCで資格情報によるアクセス、実 negotiated SMB dialect / signing / encryption、コピー・内容SHA256・再読戻し、権限外・匿名拒否、非許可LANから接続不可、Gserver Docker/WSL既存保存機能正常を実測。Windows再起動後の動作を別途確認。

## 構築前と構築後の区別
現在 **SMB共有は未作成 / 家庭内転送はNOT_VERIFIED**。TCP445 listenerが存在しても、FirewallによるLAN到達許可やWAN閉鎖の証拠ではない。独自リバースプロキシ/Docker SMB gateway/VPNを今すぐ新設する根拠もない。

参考: Microsoft「Windows Server の SMB トラフィックをセキュリティで保護する」 https://learn.microsoft.com/ja-jp/windows-server/storage/file-server/smb-secure-traffic
Microsoft「SMB セキュリティの強化」 https://learn.microsoft.com/ja-jp/windows-server/storage/file-server/smb-security
Microsoft「Windows 10 サポート終了」 https://support.microsoft.com/ja-jp/windows/deployment/updates-lifecycle/windows-10-support-has-ended-on-october-14-2025

## 2026-10-28 master PC read-only security audit

Master実測: `scripts/windows_lan_security_readonly.ps1` 実行 `VERIFY=PASS` は監査処理が正常終了した意味であり、安全な共有の合格ではない。観測値: `SMB1_OPTIONAL_FEATURE_STATE=NOT_VERIFIED`、`SMB_SIGNING_REQUIRED_REGISTRY=0`（このPCでは署名の必須を示さない）、`SMB_SIGNING_EFFECTIVE=NOT_VERIFIED`、`SMB_SHARE_ENCRYPTION_EFFECTIVE=NOT_VERIFIED`、`BROAD_WRITE_ACE_COUNT=2`、`ACL_UNRESOLVED_IDENTITY_COUNT=0`、`FIREWALL_445_REMOTE_SCOPE=NOT_VERIFIED`、`ROUTER_WAN_445_FORWARD=NOT_VERIFIED`、`WIFE_PC_SECURITY_PATCH_STATUS=NOT_VERIFIED`、`CHANGES=NONE`。

Broad Write 2件はEveryone/Authenticated Users/Builtin Usersの許可を簡易カウントした値だが、shareとNTFSの実効アクセスや外部公開を証明するものではない。親フォルダーからの継承/ACLの種類を匿名・最小出力で判定する `scripts/windows_lan_acl_detail_readonly.ps1` を追加。本人のWindows user名とファイル名は出力しない。**既存ACLはまだ編集しない。**

## 2026-10-28 NTFS inherited ACE readback and narrow intake design

PC実測で `G:\\GserverStorage` および `G:\\GserverStorage\\files` は **NTFS**、ACL継承無効化はしていない。双方で `Authenticated Users` のALLOW Write相当 ACEが **2件・すべて継承**。これは4個の個別の無防備な共有を意味せず、SMB経由の実効アクセスもこの出力だけでは決まらない。親G:のACLを変更しない。親に広範Modifyが残るため、子だけ継承を遮断しても親からのDeleteChild等の実効権限まで遮断できたとは断定しない。

新設するネットワーク受信用の候補は **`G:\\GserverStorage\\files\\LAN-Inbox` のみ**（既存の `README.md` が置かれた `files` 全体は共有しない）。`scripts/windows_lan_inbox.ps1` は明示 `-Prepare` で未存在の空子ディレクトリを作るだけで、その子の継承保護・SYSTEM/Admins/Owner限定ACLをreadback。SMB share、User、Windows Firewall、Router、Dockerは未変更。既存フォルダーの保護状態を勝手に改修せず拒否する。親側を安全化せずに「完全に独立したセキュアボリューム」と呼ばない。LANの実効アクセスは専用share ACLとNTFS ACLの積、およびFirewallのwife PC限定で追加検証。ロールバック時にユーザーのファイルを自動削除しない。

## 2026-10-28 LAN-Inbox PC acceptance and upcoming network gates

Actual Windows11 readback after `windows_lan_inbox.ps1 -Prepare`: **CREATED**, `INBOX_INHERITANCE_PROTECTED=True`, `INBOX_BROAD_ALLOW_COUNT=0`, `G_PARENT_ACL_CHANGED=False`, `SHARE_CREATED=False`, `FIREWALL_CHANGED=False`, `VERIFY=PASS`. Unit source contract 2/2 PASS. This is new-folder ACL readback, **not** proof of complete ACL isolation from parent DeleteChild privileges, successful Samba/NTFS read inside Docker, or wife-PC LAN access.

Two follow-up **read-only** probes are implemented: `scripts/windows_lan_firewall_readonly.ps1` on Master PC counts active inbound TCP445 permit rules including broad remote scopes; `scripts/windows_wife_lan_readonly.ps1` on wife PC reads Windows build and LAN IPv4 candidates. Both avoid source file edits, usernames/passwords/MACs and network changes. Windows10 ESU enrollment remains **NOT_VERIFIED** unless observed separately. SMB3 encrypted network share creation/rollback is not executed. Do not enable unbounded firewall allow merely to make transfer work.
