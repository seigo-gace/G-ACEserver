# CURRENT｜G-ACEserver
## 2026-10-28 Windows LAN事前検査：SHARE_NAME RemoteException修正

- **実PC:** 2026-10-28 Master Windows11。GitHub `4b3bdaf...` まで fast-forward後、`WINDOWS_LAN_SMB_LIGHTWEIGHT_PREFLIGHT` 実行。`TARGET_DIRECTORY=YES`、`SMB_SERVER_SERVICE=Running`、`SMB1_REGISTRY_VALUE=REGISTRY_UNSET`、`SMB2_REGISTRY_VALUE=REGISTRY_UNSET`（**実際のSMB1/2有効無効とは同義ではない**）、`PRIVATE_PROFILES=1`、`PUBLIC_PROFILES=0`。その後 `PHASE=SHARE_NAME`→`FAILED_PHASE=SHARE_NAME`→`ERROR_TYPE=RemoteException`→`CHANGES=NONE`→`VERIFY=FAIL`。TCP 445未到達、共有名の衝突有無は不明、LAN転送未開始。Gserver Docker/G:保存の既存PASSはそのまま。
- **原因候補/修正:** Sourceで共有名の存在確認に `net.exe share GserverTransfer 2>$null` を使用。PowerShell停止優先 `$ErrorActionPreference='Stop'` では「共有が存在しない」場合のnative stderr処理が `RemoteException` を出すため誤停止し得る。Windows環境固有の詳細がないため根本を断定しない。**コマンドを取り除き**、HKLM `SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Shares` 内の単一名称 `GserverTransfer` の値存在を.NETの読取専用APIで判定。キー自体が読めなければ `UNKNOWN` を表示し、誤って「空き」と言わない。共有名の取得以外のフェーズ・設定は変更しない。Commit `c67f622bbb0b88d7ceeb2d2906fb300d86ac6278`。
- **Exact Next:** Master PCのSourceをfast-forwardし `scripts/windows_lan_preflight.ps1` のReadOnly再実行（大規模再テスト、Docker再build不要）。TCP445と共有名readback後、実共有・NTFS ACL・認証・Firewallを対象Host最小権限で実装。以前のG: dedicated folderのみ対象、SMB1/Guest/Everyone無制限・WAN公開は禁止。Dev KB/TGS進捗は独立で継続。

## 2026-10-28 Windows LAN事前検査：OutOfMemoryException→軽量段階式へ修正

- **PC実測:** MasterがPowerShellでGitHub `4f3e026...` へfast-forward後、`scripts/windows_lan_preflight.ps1` 初回実行。結果 `PROJECT=Gserver`、`ACTION=WINDOWS_LAN_SMB_READ_ONLY_PREFLIGHT`、`ERROR_TYPE=OutOfMemoryException`、`CHANGES=NONE`、`VERIFY=FAIL`。初期版は単一try内で `Get-SmbServerConfiguration`・`Get-NetConnectionProfile`・**無制限の `Get-SmbShare` 全列挙**・`Get-NetTCPConnection` を実行し、失敗段階を出していなかったため、**どの操作でメモリ例外になったかは未確定**。Windows自体の物理RAM不足と断定しない。Gserver Docker/Volume・G:実ファイル保存は前回PASSのままであり、LAN共有を作成した証拠はない。
- **Source改修:** `scripts/windows_lan_preflight.ps1` をcommit `ed918f02c61fe52598060997de1ae2b5d0b064d4` で軽量化。フル共有一覧と重いSMB CIM設定取得を廃止し、対象G:ディレクトリ存在/reparse、`LanmanServer` Service、SMB1/2レジストリ値（未設定なら `REGISTRY_UNSET` として推測しない）、接続プロファイル、固定共有名の競合を `net.exe share GserverTransfer` で調べる方式、.NETのローカル TCP445 listener に置換。各フェーズ前に `PHASE=...`、失敗時 `FAILED_PHASE=...` と例外クラスだけ表示し、ホスト固有IP・資格情報は出さない。全て読取専用、LAN共有作成/Firewall変更なし。
- **Exact Next:** 実PCで最新Sourceへfast-forwardし同スクリプトを再度1回だけ実行。PASSなら実観測したService/Profile/445/共有名の条件に基づきSMB共有とNTFS ACLの最小化設計に進む。FAILなら `FAILED_PHASE` の箇所だけ調査・修正し、全体テスト/再ビルドはしない。WindowsのPublic→Private、SMB1、ゲスト、Everyone書込の勝手な有効化をしない。実転送/家族PC読戻し・Dev KB/TGSは未検証。

## 2026-10-28 家庭内動画転送：Windows標準SMBを再利用・読み取り専用事前検査Source

- **新しい実行物:** `scripts/windows_lan_preflight.ps1` をコミット `5ad80bd2fa407b50d3795c79eba5c22d1824de5c` でGitHubへ追加。Master Windows 11 Host側で `G:\\GserverStorage\\files` の実ディレクトリとreparse拒否、SMB Serverサービス、SMB1/SMB2設定、アクティブなPrivate/Publicネットワークプロファイル、共有名衝突・既存対象共有・TCP445 Listen状態を**読み取り専用**で検査。原則GACE_RESULT包みで結果返却し、設定/パスワード/個別ローカルIP/他shareの実名を記録しない。Host実行は未受領。
- **設計判断:** 妻Windows 10から同じ家庭内Wi-Fi経由で4TB級動画を送る実用経路は、不要なGserver HTTP書込みAPI/Web管理UIを追加するよりWindows標準**SMB2/3の認証付き共有**で `G:\\GserverStorage\\files` のサブツリーだけを対象にする。既存Gserver HTTPは `127.0.0.1:18765` のまま。SMB1や匿名/ゲスト/Everyone無制限を有効化しない。**共有を作る/Firewallを変更する/ネットワークPublic→Privateを変更する操作はまだ実施していない**。その前に本人ホストの実設定とLAN到達の境界・専用Principal・NTFS ACL・無断公開の危険・復元経路を検討。
- **Exact Next:** Master PCで `git pull --ff-only` 後に `powershell.exe -NoProfile -ExecutionPolicy Bypass -File G:\\Project\\Gserver\\repository\\scripts\\windows_lan_preflight.ps1` を実行して readback。実行結果で安全な既存条件を判断し、最小ACL・認証付きLAN共有・元に戻す機能へ進む。未検証共有を作成済みと報告しない。
 
## 2026-10-28 G:実ファイルコピー初成功｜保存・SHA256照合・認証付きAPI読戻しPASS

- **Master PC実測**: WSL Ubuntuで `git pull --ff-only` により `ebd4ce3...` へfast-forward。最新 `app/storage.py` のcontextmanager修正を含む `python3 -m unittest discover -s tests -p test_gserver_files.py -q` = **5/5 PASS**、`python3 -m unittest discover -s tests -p test_storage.py -q` = **9/9 PASS**。Host CLI `python3 scripts/gserver_files.py put README.md` が `{"bytes":6226,"name":"README.md","sha256":"171b13dcef1bfd851eb88a3dd1090ff0a9a119e54850bab3cf58e90795a0bdeb"}` を返し、`cmp -s README.md /mnt/g/GserverStorage/files/README.md` 成功。CLI `list` = `README.md` file size 6226。sudo認証後のDocker `gserverctl.py storage-list` で認証付きAPIから同一実ファイルを読戻し。**`GSERVER_FILE_COPY=PASS`**。
- **受入判定:** 単一ローカルファイルの `put`→G:指定子フォルダーへの**非上書き実書込み**→bytes/SHA256→OS同一比較→Dockerで認証済みAPI一覧、実PCでPASS。既存 `GserverStorage/files` の他ファイルやF:の原本は触らず、旧8765サービス/現18765ポート維持。再buildや新規有料AI/定期タスク不要。
- **未完:** `get` の実G:読戻しをローカル別ディレクトリへ行った証拠はまだない。奥さんのWindows 10端末からLAN転送・共有ユーザー権限・Windowsファイアウォール/Privateネット判定・SMB認証・大容量動画の断続再開/速度/空き容量/クォータ・Windows再起動後自動復旧、Dev KB・TGS・バックアップ/復号隔離復元は**NOT_VERIFIED**。F01–F08全体完成とはしない。
- **NEXT:** MasterのWindows 11・妻Windows 10の既存LAN環境をread-onlyで検査し、G:の単一許可フォルダーのみ**認証付き**SMB共有で転送できるよう安全な承認・ロールバック操作を設計する。Gserver 18765 HTTPは今まで通りPC内loopback限定、外部公開しない。SMB1/ゲスト共有/無制限Everyone書込/Firewall全開/家庭内ルータのポート転送は行わない。大容量転送はまずWindows標準SMBを再利用し、サーバー固有の独自HTTPアップローダーを重複実装しない。独立して実装できるDev KB/TGS連携にも継続着手。

## 2026-10-28 S3ファイル転送｜PC unit error 3件を診断し共有Storage例外境界を修正

- **実PC観測:** Masterの `git pull --ff-only` によりHost checkoutが `3c3aaa2...` へfast-forward。`python3 -m unittest discover -s tests -p test_gserver_files.py -q` が `Ran 5 tests` 中 `3 errors`。ケース `test_existing_symlink_and_out_of_scope_paths_rejected`、`test_failed_partial_write_leaves_no_published_file`、`test_round_trip_hash_and_no_overwrite` で本来 `FileExistsError/OSError` を報告する場所に `storage.StorageUnavailable` が発生。そのため `&&` により `put README.md` とG:実書込・CLI list・Docker storage-listは**一切実行されていない**。既存Docker/Volume/API read-onlyの前回PASSを否定しない。
- **根本原因:** `app/storage.py` の `@contextmanager Storage.directory()` と `open_file()` が `yield` を `try ... except OSError` 内に入れていたため、呼出し元のファイル重複拒否や書込ディスク満杯まで mount失敗 `StorageUnavailable` に誤変換する構造バグ。単にtestの期待値を変更して隠さず、**directory/fileのopen+fstat段階のOSErrorのみStorageUnavailableへ変換し、yield後の利用者操作エラーはそのまま伝播**するよう実コードを修正。既存のpath traversal/リンク/mount拒否、close確保は維持。さらに `tests/test_storage.py` で `yield` 内でFileExistsErrorとENOSPCを発生させて伝播を確認する新unit追加。**Source commit `8be1c0e6730adc5e27815a1f56e4256b689ac1a9`**。
- **現状と次:** GitHub Source修正は完了しPCの新test/実G:ファイル書込みは**未検証**。次は clean checkout→`git pull --ff-only`→**S3転送5 test+Storage unit**のみを実行してから、既存 `README.md` を新規保存（同名存在ならfail-closed）→CLI `list`→認証付きDocker `storage-list`、結果照合。旧Docker imageは変えないので再buildしない。既存G:原本/旧8765/LAN/KB/TGSは未変更。

## 2026-10-28 G:専用Docker readback実機PASS・Host CLIファイル転送Source追加

- **Master PC実機:** Windows PowerShell → WSL `/mnt/g/Project/Gserver/repository` `git pull --ff-only` で `13fff7a...` へ進め、Python `33 tests in 17.054s OK`、`sudo -v`、`python3 scripts/gserverctl.py enable-storage`（既存専用Docker container `gace-gserver-gserver-1` healthy）、`python3 scripts/gserverctl.py storage-list` → `{"entries":[],"next":null}`、`status` → `127.0.0.1:18765->8765/tcp`、末尾 `GSERVER_STORAGE_READ=PASS`。**Windows G:の専用子フォルダーがDockerに読み取り専用接続され、認証済みAPIから一覧を取得できた。** データ未登録のため空一覧は正常。元のG:全体やF:原本への接続ではない。
- **Source進捗:** 今回は既存GserverのDocker image/Volume/認証/Host 18765はそのまま維持。非破壊のHost WSL CLI `scripts/gserver_files.py` を追加。操作 `put LOCAL_FILE` は実G: mount確認・既存Storageの許可subtree/パス検証・symlink拒否・1MiBチャンクのstream copy・SHA256・fsync・ハードリンクで原子的な**新規保存のみ**・既存ファイルを上書きしない・部分ファイルの通常エラー時削除。`get NAME DIRECTORY` は保存側も新規作成のみ。`list` は既存StorageのAPIと同じ境界を使用する。コードはG:の **`GserverStorage/files` のみ**に保存し、他フォルダー、Docker volume、F:の原本は変更しない。Unit `tests/test_gserver_files.py` にreadback/重複拒否/禁止path/mount切断/途中disk full時のcleanupを追加。
- **証拠区別:** Source commit `c5777a3e0fdf1c00a5fdcafcb74062096b04bf36`。**Host CLI転送の新unit/実G:転送はまだ未検証**であり、既存の `GSERVER_STORAGE_READ=PASS` を新CLIのPASSに転用しない。Gserver自身のHTTPはまだ読み取り専用であり、別PCからのLAN送信・書込みHTTPアップロード・resume・削除/更新/クォータ/暗号化backup/KB/TGSは未完成。4TB大容量転送の速度・中断回復は未測定。
- **Exact Next:** 新CLI unitだけを実PCで実行し、G:\\専用ディレクトリへ小さな既存README.mdを1ファイル実保存して、`gserverctl storage-list` で認証付き実読戻し。新image再ビルド不要。これを確認後、より実用的なファイル送受信・Windows内/家内LANからのアクセス・Dev KB/TGS・隔離復元へ継続。定期Codex/別AI・追加管理UIは不要。

## 2026-10-28 S3 storage test blocker｜稼働中18765ポート競合のテスト誤判定を修正

- **PC実測:** `git pull` で `49c5b11...` へfast-forward後、`python3 -m unittest discover -s tests -p test_runtime.py -q` を実行。`32 tests` のうち `test_local_enable_disable_reuses_image_and_volume`、`test_local_failure_recovers_original_profile`、`test_switch_to_loopback_recreates_container_with_volume_preserved` が `OSError: [Errno 98] Address already in use`（`127.0.0.1:18765`）で失敗。**Gserverは既に18765番で稼働しているので正常な競合**。テストが実host socketをbindする欠陥で、Master/本番Gserver/ストレージ障害ではない。`sudo -v`以降は `&&` 連結で未実行なのでG: storage未接続のまま。既存serviceを止めたり、ポートを変えたりしてテストを通してはいけない。
- **GitHub Source修正:** `tests/test_runtime.py` の該当3ケースで `ctl.socket.socket` のport probeだけをmockし、**実稼働18765へ依存しない**よう変更。反対に、port conflict時は実Dockerへ一切触れず拒否することを確認する独立unitを追加。Commit `1c889e7ecc29f02cd850aa58ad30440c8bf1d3a3`。GitHubで変更後コードを読戻し確認。**PC unit再実行/Storage API実機成功はこれから**。
- **Exact Next:** PC clean Git→`git pull --ff-only`→対象unit（33件想定）→sudo→`gserverctl.py enable-storage`→`storage-list`→`status`。稼働中127.0.0.1:18765公開/既存Volume/image/旧serviceの保持を尊重。成功後にG:実ファイル送受信・Dev KB・TGS・隔離復元の未完成条件へ進む。失敗時は今回と違う箇所だけ修正し、重複した隔離smoke/再ビルドはしない。

## 2026-10-28 実PCローカルHTTP成功・G:専用読み取り接続を実装

- **Host実測PASS:** MasterのWSL Ubuntu checkoutがGitHub `8090474...` までfast-forward。Python unit `28/28 PASS`、`sudo` PASS、`gserverctl.py enable-local` → Docker network `gace-gserver_gserver-local-v2` Created → Container `gace-gserver-gserver-1` Healthy。`docker port ... 8765/tcp` が **`127.0.0.1:18765`**、`curl http://127.0.0.1:18765/health` が **`{"status":"ok","service":"gserver"}`**。Compose `status` は `127.0.0.1:18765->8765/tcp`、末尾 **`GSERVER_LOCAL=PASS`**。PC Runtime接続ゲート合格。**Windows側のlocalhost到達/Windows再起動後自動再開はまだNOT_VERIFIED**。旧プロトタイプの8765・G:原本・TGS未変更。
- **S3 GitHub実装（実機未検証）:** 既存イメージの `/files` `/download` 読み取りAPIを再利用し、`gserverctl.py enable-storage` / `disable-storage` / `storage-list` のCLIを追加。**固定専用 `G:\\GserverStorage\\files`**（WSL `/mnt/g/GserverStorage/files`）だけ作成し、Dockerへ親 `/mnt/g/GserverStorage` を `/mnt/g` として**read-only bind mount**、他のG:フォルダー/F:の原本を渡さない。WSL `/mnt/g` のmount証拠無しならfail closed、シンボリックリンク/別deviceは拒否。API bearer tokenは既存Docker永続volume内に非root0600権限でランダム生成して保持、公開GitHub/ログに出さない。compose snapshot別SHA・release ledgerのstorageフラグを維持、停止/再起動/rollbackは同じ永続Volumeを再利用。元imageの再ビルド不要。**本番動作・実ドライブのPermission/readbackは未受領**。
- **受入境界:** 読み取り専用の専用フォルダー実利用を先に完成。アップロード/更新/削除・別PCからの転送・Dev KB/TGS・暗号backup/restore・Windows再起動後の持続起動は未実装/未実証。F01～F08を完了扱いしない。不要Web管理UIや重複CI/重い検証は増やさない。
- **最短Exact Next:** MasterのPowerShell→WSLから clean check・`git pull --ff-only`・対象unitだけ・`sudo -v`・`gserverctl.py enable-storage`・`storage-list`・`status` を1回実行し、実G:マウントとDocker側認可APIのreadback。必要に応じてWindows PowerShellから `http://127.0.0.1:18765/health` 到達も確認。失敗時は対象原因に絞って修正。次は実ファイル送受信・既存Dev KB・TGS・復元を優先。

## 2026-10-28 ローカルHTTPポート公開失敗→原因特定・修正反映（PC再確認待ち）

- **実機失敗:** Masterが `git pull --ff-only` で `6690bfe...` に更新後、`tests/test_runtime.py` Python **26 PASS**、`sudo` PASS、`python3 scripts/gserverctl.py enable-local` で `Network gace-gserver_gserver-local Created`、Container `Healthy` を確認。しかし `curl http://127.0.0.1:18765/health` は `curl: (7) Failed to connect`。再実行しても status の PORTS は **`8765/tcp`だけ**でホスト公開無し。**GSERVER_LOCAL=PASSは出ていない。** Docker service本体は保持中。原因を「ユーザーがポートを閉じた」と扱わない。
- **原因:** Docker Engine 29系 + Compose 5系の `internal: true` bridge 単独接続では、host-local publish要求が無視される報告（moby/moby discussion #53256）と完全一致。既存Controllerは`access=loopback`をledgerへ保存しても新実体へのnetwork/port反映を検証せず、2回目の`enable-local`で`ps`だけを返すため自己回復できなかった。
- **修正Source:** `scripts/gserverctl.py` のloopback用snapshotを **新Manifest `*.loopback-v2.json`** で作成。新たに `gserver-local-v2` **通常bridge** に接続（従来の内部のみのネットワーク設定との衝突回避）、Host公開は**`127.0.0.1:18765:8765`固定のみ**。これはContainer outbound制限を旧`internal: true`と同一にはしないため、外向き通信防止が別途要件ならHost FWで検証する。局所公開とは区別する。image/Volume/old immutable snapshotsは削除しない。profile変更時`docker compose up -d --force-recreate --wait`を使い、失敗時旧版への強制再作成rollback。既にledger `access=loopback` のときも `enable-local` により再適用できる。回帰Unit **2件追加**、既存unitのnetwork期待更新。Commit **`8b7235164905558b7e30968f997b67b116780bd1`**。Source実装済み、**新修正のPC unittest/Runtimeは未受領**。
- **Exact Next:** Master WSL `/mnt/g/Project/Gserver/repository`のclean state確認→`git pull --ff-only origin main`→変更のPython unittestのみ→`sudo -v`→`gserverctl.py enable-local`→`docker port ... 8765/tcp`でHost publishの実測→WSL `curl --fail http://127.0.0.1:18765/health`→Windows→WSL localhost forwarding確認。**同じ旧失敗コマンドをそのまま再実行させない**。合格後にG:マウント/本人の認可パスに進み、既存KB/TGS接続/復元を続ける。CI/本番G:/KB/TGSはNOT_VERIFIEDのまま。
 
## 2026-10-28 ローカル専用HTTP接続｜Source実装済、PC動作確認待ち

- CHATが既存 `scripts/gserverctl.py` に `enable-local` / `disable-local` を追加。固定の **`127.0.0.1:18765:8765`** だけを公開するバージョン別SHA256固定Compose snapshot (`*.loopback.json`) を作成し、Docker networkは `internal: true`、既存Volume/image/release ledgerを維持する。ポートが埋まっていたら変更前に拒否。既存の8765/Python試作や他サービスを止めない。`start|stop|status|logs|rollback|recover` は選択中のlocal/isolated構成を再利用。`disable-local` で元の隔離構成へ戻す。**GitHub Source commit `16ca27d3ec7d053219e9ecb30fcdef389265a973`、回帰Unit 4件追加。PC実行・テストは未受領。**
- **即実機NEXT:** Master既存WSL checkoutで `git pull --ff-only origin main` → `python3 -m unittest discover -s tests -p test_runtime.py -q` の対象変更回帰テスト → `sudo -v` → `python3 scripts/gserverctl.py enable-local` → `curl -fsS http://127.0.0.1:18765/health` → `status`。変更/依存が不一致ならfail closedして原因箇所を修正する。以前PASSの隔離Runtime試験再実施・image再ビルド・Volume削除・Windows C:再調査は行わない。HTTP `/health` は非公開環境での通信経路確認に限り、G:/KB/TGSが使える証拠ではない。
- この後、必要に応じてMasterから最小限の `/mnt/g` 実mount/readbackを取得し、認可対象subtree/秘密の安全なローカル注入だけを最小構成で仕上げる。公開RepoにHost秘密/実データを書かない。Windows reboot証拠未受領。

## 2026-10-28 S2正式Dockerコンテナ起動 PASS｜次はローカル接続・G:マウント

- **Master PC実測:** Windows PowerShell `wsl.exe -d Ubuntu -u gace -e bash -lc ...` から、検証済みアプリ/Compose/Controllerに差分がないことを確認し、`sudo docker --host unix:///var/run/docker.sock build --quiet --network=none` → `python3 scripts/gserverctl.py activate` → `status` を実行。`GSERVER_ACTIVATION=PASS`。専用Volume `gace-gserver_state` **Created**、専用Container `gace-gserver-gserver-1` **Up (healthy)**、image `sha256:3216607d7a54dd3daec5e6e88318e921f296b1ef650039f4195dc5c7122b7880`。**試験用ではなく実運用Controller管理下で起動中**。旧原本や他Service、G:の実データを触っていない。
- **重要:** base Composeは `network_mode:none` + published port無し + G:/F: bind無し + auth credential未注入。現時点の `healthy` は**内側で/healthが200**のみ。通常ユーザーがWindows/WSLからHTTP接続できる、ファイルが使える、Dev KB/TGSが使えるという意味ではない。管理用CLI `scripts/gserverctl.py status|logs|stop|start` は本稼働Projectを対象にして使える。永続Volumeを消す `docker compose down -v` 等は厳禁。
- **直近完了条件:** (1)既存host listening ports 8765と別port(例18765)の空き状況、および `/mnt/g` の実mount状態を最小限read-onlyで確認。(2)前段の固定immutable imageとrelease ledger/rollbackを壊さず**127.0.0.1限定HTTP公開**と管理者本人が指定したG:サブツリーへの最小権限bindを追加。(3)host HTTPヘルス/認証/Storage readback、既存service退行無し、Docker CLI restart/rollbackを実機確認。必要な秘密・実データパスは公開Repoに登録しない。(4)既存Dev KB・TGS・Backup/Restoreへ進める。**同じ隔離テストや同一Docker buildは繰り返さず**、管理UIを新規開発しない。Codexを自動起動・委任しない。
- **注意:** Windows Host再起動後のWSL+Docker自動起動、実G:接続、外部TGS・KBは今なお未検証。F01–F08完成とは扱わない。

## 2026-10-28 Gserver S2隔離実機検証 PASS｜初めて実コンテナ起動を実証

- **証拠:** Masterから Windows PowerShell → `wsl.exe -d Ubuntu -u gace` で一括実機試験 `bash scripts/verify_pc_runtime.sh` の完全な出力を受領。試験時PC source `SOURCE_SHA=6db18616b81fc158a553ee455c38cca15358c2a6`。**Python unittest 60/60 PASS、UI挙動4/4 PASS**、旧原本SHA固定stagingは実Docker container Healthy / internal `STAGING_HTTP=200` / host ports NONE。新packaged imageは実Docker build成功、専用隔離Container Healthy、再作成・stop/startのhealth、Volume内sentinel永続化PASS。
- **実Controller:** 違うimage IDへの更新→元image IDへrollback→stop/start→同じVolume sentinel維持を実Dockerで確認。`CONTROLLER_SMOKE=PASS;IMAGE_UPDATE_ROLLBACK=PASS;PERSISTENCE=PASS;HOST_PORTS=NONE`。結果 `SUBCHECK_VERIFY=PASS;RUNTIME_SMOKE=IMAGE_RECREATE_PERSISTENCE_OFFLINE`、`LOCAL_VERIFICATION_RECEIPT=SAVED`、最後に `VERIFY=PASS;SCOPE=ISOLATED_SOURCE_AND_PACKAGED_RUNTIME;F01_F08=NOT_COMPLETE`。試験専用コンテナ/Volumeはcleanupで削除、既存Host service回帰ガード含む。認証の問題は今回解消。
- **SHA整合:** 検証時 `6db18616b81fc158a553ee455c38cca15358c2a6` からGithub最新main `bdf16abcc10866e7d4088605f0a12b0f5ff63a7e` までの差分は `AGENTS.md`、`docs/CURRENT.md`、`docs/requirements/FINAL_ACCEPTANCE.md` の**文書3ファイルだけ**。実行コード差分なし。そのため上記Runtime証拠は隔離Runtimeの現ソースに適用可能。ただし新機能/本番への証拠流用は不可。
- **受入範囲:** GSR-S2-02の隔離Docker build/起動/volume永続化とGSR-S2-05の実コントローラー更新・旧版差戻し（同じアプリのfixture）は実機PASSへ昇格。完全なS2本番配置（ユーザー手元からアクセス可能なloopback listener/必要なcredentialと最低限のG: subtreeのみ承認済みでmount/WSL起動連動）やS3ストレージ実体・F04 KB/F05 TGS/F05 Backup&Restore/F08 E2Eは**未実装/未検証**。テスト用環境は終了しており、通常利用Gserver本体が常時起動したとは宣言しない。CIは未実行。
- **最短Exact Next:** staging/隔離smokeを再度求めない。**VS Code/Cursor CLI-first**で利用するGserver本体の**ローカル限定**配置を、既存ポート/サービス/設定/セキュリティ競合を非破壊で照合したうえで実装・有効化して、実利用者の `start/status/logs/stop/rollback` を実機で検証する。既存HTML管理画面の拡張・Codex自動定期タスクは不要。その後、G:上の明示許可subtreeへの安全なStorage接続・読み書き、既存Dev KB実接続、TGS/暗号backupと隔離restore、WSL再起動/失敗復旧へ進む。検証受領後も同じテストを反復して進捗にしない。

## 2026-10-28 Windows/WSL実機ディスク監査｜前回の+37GB判断を撤回

- **最優先の訂正:** PowerShell `Win32_LogicalDisk`実機readback: C:総容量 **117.86 GiB**、使用 **82.47 GiB**、空き **35.38 GiB**。D:総容量 **465.66 GiB**、使用 **48.98 GiB**、空き **416.68 GiB**。Masterの「整理後C:使用量約80GB」と同じ単位で比較した概算差は**約+2.47GiB**。CHATが「117GB使用し、約37GB増」と記録したのは**総容量を使用量と混同した誤り**で、ここに明確に撤回する。元80GBの測定時点/丸め/単位は未確認のため、増加原因や厳密な差分はこれ以上断定しない。
- WSL distro登録の実物: `Ubuntu`, `\\?\D:\WSL\Ubuntu\ext4.vhdx`、**10.13GiB**。D:へのWSL移設は既にできている。Ubuntu内のDocker `DockerRoot=/var/lib/docker`、`docker system df`: Images **193.9MB**、Build Cache **191.3MB**、Containers **0**、Volumes **0**。`df -h /`: WSL rootの使用約**8.0GiB**。**Dockerの大量データがC:を約37GB消費したという仮説は否定**。ただし物理C:の全ファイル増減の時系列証拠はない。
- 観測したC:内候補サイズ（占有容量であり、最近の増加分ではない）: `hiberfil.sys` **7.95GiB**、Windows Update download **4.06GiB**、VS Code roaming **2.46GiB**、VS Code extensions **1.63GiB**、Codex `.codex` **1.12GiB**、User Temp **0.83GiB**、Cursor Roaming **0.25GiB**、Docker Local **0.04GiB**。重要データ/既存開発の作業状態を含みうるので推測で削除しない。
- **NEXT:** Codexへの「+37GB緊急原因調査」依頼は誤認識に基づくため取り下げる。追加の重い再帰調査、Docker再インストール、WSL移設、強制キャッシュ削除は不要。C:空き35.38GiBを維持し、大容量化が実測されたときのみ対象限定の確認を行う。Codexは本来のGserver S2〜S7機能実装に集中し、本人専用CLI運用と既存データ保護を厳守。

## 2026-10-28 Master修正｜単独CLI運用・C/D配置/容量優先

- 最新のMaster意思は **単独使用でVS Code/Cursor操作のみ**。管理者Web画面は必要なし。既存UIは除去のために工数を掛けないが、これ以上管理UI機能を盛らず、CLI/Composeで起動/停止/ログ/復旧を完結させる。必要なWeb/APIは維持。F01～F08の完成条件は[FINAL_ACCEPTANCE.md](requirements/FINAL_ACCEPTANCE.md)で修正。
- **PCの確定既往:** C SSD約118GiB(前回空き約34～35GB、Master最新申告空き36GB)、D HDD内 `D:\WSL\Ubuntu`にWSL ext4.vhdx既存配置済み（当時約6.67GiB）。WSLとDockerを勝手に再配置しない。Docker Engine29.9.2はWSL内。docker/containerdの使用先、Linux mountと実Windowsディスク・image容量の2026-10-28時点readbackは **NOT_VERIFIED**。
- D: HDD上のWSL ext4領域と`/mnt/d`/`/mnt/g`のcross-filesystem I/O性能差を現物で評価し、既存親Project Git/Worktree境界を崩さず必要最小の配置最適化を行う。Docker cache/build imageの不要増加を抑制。実データ削除・Docker prune・rootdir移設・WSL VHDX移設は別途検証/権限条件まで禁止。
- **Exact Next (Codex):** ディスク容量については直上のWindows/WSL実機監査済み（C:使用82.47GiB／空き35.38GiB、WSL VHDXはD:）。重複した容量調査をせず、S2 CLI・実機runtimeの受入 → G: Storage・正式Dev KB・TGS・隔離復元の未実装を減らす。管理UI拡張や新規重い依存は避ける。Codexは時間指定自律ジョブ/別AIの起動禁止。

## 2026-10-28 Codex継続｜S2差戻し修正・S3読取実装

- Owner=Codex。再開HEAD `28281a6b516f7059df65ce1ce8ae933076a1d34a`、検証プロセスなしを確認して変更再開。旧HEADの結果が後から届いた場合は、そのHEADの証拠として扱い、新しい実装のPASSへ転用しない。
- **S2 Source:** sudoでimage環境変数が失われる経路を修正。image別のCompose snapshotをローカルへ原子的保存/hash検査し、後日のソース変更から起動/差戻しを分離。Docker接続はPCのUnix socketへ固定。実controllerの更新/差戻し/volume保持を検証する隔離smokeを一括試験へ追加。
- **S3 Source:** 明示許可されたmount配下の一覧/ページ分割/ストリームdownload/Range、traversal・symlink・hardlink・特殊ファイル・Windows alias拒否を実装。UIのフォルダー移動/保存/再試行/ログアウト取消、応答と安全な監査ログのrequest IDを追加。`GSERVER_FILES_ROOT`未設定では無効、実G:/F:への接続・変更なし。[S3契約](architecture/STORAGE_S3.md)。アップロード/更新/削除は未実装。
- **検証:** Python 60件、既存Windows Nodeを利用したUI挙動4件、snapshot Compose config、bash構文を検証。Dockerをmockした試験・mountを模擬した合成ファイル試験を含み、実機コンテナ/実USB/browser E2Eではない。正確な終了結果は本変更のIssue #9記録に記載。
- **証拠継続:** `verify_pc_runtime.sh`がローカルstateの`gserver/verification/latest.json`へHEAD/phase/exit/timestampだけを保存する。生ログ/秘密なし、ソース変更時PASS禁止。同じ検証を再依頼する前にreceiptを読む。
- **PC Runtime:** 元ソースSHA不変。sudo認証は引き続き本人端末が必要で、更新版Docker起動/永続性/実rollback未確認。実行結果未受領をPASSとしない。新しい検証の重複要求はしていない。
- **CI/TGS/Backup-Restore:** 未実行/未実証。S4既存KB・S5接続権限/暗号backup・S6監視・S7再起動/復元を完了扱いしない。F01–F08と46タスクを維持。
- **Exact Next:** 最新HEADの一括検証receipt/結果を照合→失敗箇所だけ修正・必要範囲再検証→S2正式配置/ingress/Windows持続稼働。安全に独立可能なS3以降の実装は継続。原本/秘密/公開設定/Contabo/既存サービスには変更なし。

## 2026-10-27 Codex実測・S2ソース実装（現セッション）

- **Owner / Tasks:** Codex、GSR-S1-04/S2-01/S2-02/S2-05の実装差分。開始時main `8e2dcaa19da67f04feb5f9ea2608d62d8bcbe497`。F01–F08 / 46タスクは未完了のまま。旧記録は履歴として保持する。
- **Source:** 既存試作SHA一致を確認し、原本を変更せず`app/gserver.py`へ取り込み。stdlibを再利用し、ローテーションログ、認証必須状態API、未mount時503、状態確認UI、接続数/timeout上限を追加。digest固定Dockerfile、永続volumeのCompose、image ID固定の起動/停止/更新/差戻し、更新中断journal/recover、隔離再作成・ログ永続性smokeを実装。[S2実装契約](architecture/RUNTIME_S2.md)。公開port・実データmount・秘密の作成はなし。
- **Local tests:** WSL上の全41 Python unittest PASS（既存staging10件を含む）。bash構文とCompose config PASS。HTTPテストは一時loopbackサーバーと合成認証fixture、ライフサイクルはDocker境界mock。隔離smokeの既存volume拒否・起動失敗時ログ/cleanup・cleanup失敗伝播もfake Dockerで4件検証。コンテナ起動の証拠ではない。
- **PC Runtime:** WSL/Compose v5.6.1、元ソースSHA一致、既存4サービスactive、旧8765待受なし。staging実行は`SUDO_ACCESS_FAILED`/exit16で停止、Docker socketへの非sudoアクセスも拒否。コンテナ起動・ログ永続性・image rollback・再起動後稼働は **NOT_VERIFIED**。管理者認証を迂回せず、既存サービスへの操作なし。
- **CI:** この変更のCIはNOT_RUN。新Workflowは作成していない。
- **TGS / KB:** 正式Repoの既存契約を読取照合。KBのMVS/単一Currentを再利用し、TGS ZERO/vNextを区別する。Gserverの接続権限・受領先・実送受信は未確認。新Reader/新検索基盤/Project ID流用/既存秘密コピーなし。
- **Backup/Restore:** NOT_IMPLEMENTED / NOT_VERIFIED。永続volumeの再作成試験はバックアップ復元証明と扱わない。
- **Rollback:** 元PCソース/設定/データ/サービスは無変更。新ソースは導入前。controllerは前imageへ差戻し、途中中断はjournalから`recover`、volume削除なし。ただし実Dockerで未実証。
- **Exact Next:** Master端末で`bash scripts/verify_pc_runtime.sh`を実行（staging→packaged runtimeを一括検証）し、既存sudo認証で固定image/永続log/recreate/offline検証→実ログに基づく修正→認証/ingress/drive境界の承認済み設定による正式配置。続いてS3認可ファイル操作、S4既存KB、S5既存TGS+暗号backup/隔離restore、S6/S7監視・Windows再起動・全E2E。本人操作依頼済み、非同期ジョブは予約していない。

以下は前回までの履歴。

> **最新2026-10-27 23:00 JST：MasterがGserver開発を既存VS Code (WSL Ubuntu) Codexへ単発委任。** 完全な現況、未完了の隔離起動10テスト、本体/S3～S7/正式Dev KB/TGS完成条件、保護範囲は [Codex引継ぎ](CODEX_HANDOFF_2026-10-27.md) と [Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9) の冒頭を正本とする。**Docker Engine/Compose host基盤は実機PASS、Gserver本体の最新staging修正版はPC未実行**。旧見出しにある「Docker未導入」は10/23時点の履歴であり現況ではない。バックグラウンドCodex/自動レビュー/追加AI起動は許可されていない。

**判定：DESIGN_MIGRATED / PC_TRIAL_SOURCE_VERIFIED / FULL_RUNTIME_NOT_VERIFIED**

## 開発目的
手元PCのC:/D:/F:/G:を適切に役割分担し、**Windows最小Host→WSL UbuntuのDocker/Composeコンテナ主体**でWeb/API/Storage/既存Dev KB/TGSクライアント等を独立運用するGserverを完成させる。Contaboの既存Docker/Composeサーバーと共通の運用契約を保ち、追加Serverへ拡張しやすい疑似クラウド基盤とする（各Hostの実体・権限は分離）。

## 現在位置
- NotionのF01～F08完成条件とS0～S7全46タスクをGitHub文書へ移行。
- PC本体のソースコード・実サービス構成・Codex実行確認は未取込。以前のlocalhost health 200は過去の限定報告。2026-10-22の旧PC調査では既知候補でGserver名のディレクトリを確認できず、旧起動報告との配置差がある（現在のPC実測やソース不存在の証拠ではない）。
- 既存KB正本：[seigo-gace/gace-dev-kb](https://github.com/seigo-gace/gace-dev-kb)／MVS／ModuleCatalog Current。旧kb-systemは別資産。
- TGSは既存サーバーを利用する構想。Gserver→TGS実送受信・復元は未確認。
- OSSセキュリティ/監視は既存機能と不足を突き合わせ、必要最小限を採用。
- GitHub Project #1のItem登録：**NOT_VERIFIED**（このRepo/Issues作成で自動登録されたとみなさない）。
- Repoは現在Public。実機の非公開資料やSecretsを保存しない。

## 追加確定要件（2026-10-23）

Master決定：GitHubは開発管理のみに使用し、GserverのWeb/Bot/Storage/既存KB等の**通常運用はGitHub接続なしで成立**させる。Git由来の開発履歴はSource provenanceとして保持し、更新/受領とローカル通常検索を分離する。TGSは別Hostへの独立した通信依存。完成後にはRepoをPrivate化するが、今はPublicであり機密を登録しない。

受入詳細は requirements/FINAL_ACCEPTANCE.md の横断必須条件で統一。設計変更以外のPC Source/Runtime・GitHub非依存実証・Private化はNOT_VERIFIED。PC Codex/限定Server AI投入はMasterのみが判断する。

## Master確定：Dockerコンテナ主体／疑似クラウドの複数Host共通運用（2026-10-23）

- Docker Engine + Docker ComposeをGserver正式運用の主経路とし、Contabo等と**サービス定義・起動/更新/rollback・監視・秘密/volume・リソース管理を共通化**。ホストごとのWindows/WSL・パス/USB・公開/認証は差分管理。Kubernetes等の大規模管理基盤や新Token/Workflow/サーバーAIを勝手に追加しない。
- PCの`docker=NOT_FOUND`（WSL PATHの実測）は`DOCKER_RUNTIME=NOT_INSTALLED_OR_NOT_ON_PATH`であり、「Docker廃止」ではない。Podmanの存在をDocker主経路の代替決定としない。**Docker導入・Compose実起動・二Host共通運用の実機受入は未実施**。
- aaPanelは採用確定ではない。Master既定は不要/未使用であり、実機activeのため依存を最小確認してから安全に扱う。109行HTTP試作はコンテナ化完了ではない。
- 先ほどMaster実機で`/mnt/g/Project/_TelegramGroup`へのシンボリックリンク5件が全て`LINK_OK=True`、`VERIFY=PASS`。**元の5資産移動/サービス変更なし**、再利用・統廃合は別作業。正式Dev KBは`seigo-gace/gace-dev-kb`、旧kb-systemは除外。
- NEXTはS2-01 Docker/Composeの責務・配置・既存サービスとの非破壊移行単位の確定→S2-02の必要Runtime導入/実機Compose試験。F01-F08は元の番号/46タスクを維持。GitHub切断で通常運用可能なことはF08で検証。


## 2026-10-27 現状復元・整合監査（PC再実測待ち）

- **Authority:** server-core manifest SHA `fcd38e3` / GPT CHAT Rule #17、Gserver [Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9) の現在位置を2026-10-27に読み直した。GitHub Project #1へのCurrent item登録は **NOT_VERIFIED** のまま。
- **Source/Repo:** 監査開始時のGserver `main=199786cbc3212b030a4e53c49dd39dfe1f66803e`（最終更新10/23）。当時のtreeは19ファイル（docs/requirements/tasks、AGENTS、README、scripts/pc_gserver_inventory.py、tests/test_pc_gserver_inventory.py等）で、**Gserver実アプリ、Dockerfile、compose.yaml、Docker Engine導入済み証拠はRepo内にない**。PR #10/#11はmerged、GitHub Actions runs合計0。8 Stage・46タスクは受入完了を宣言できず、Stage Issuesは未完了のまま。
- **PC歴史証拠:** 10/23にWindows F:と `F:\\G-ACE-KB` 既存ディレクトリの存在を確認、`/mnt/g` mounted・Gserver 109行HTTP試作/ソースSHA一致/8765 HTTP200を当時実測、Telegram5リンク `_TelegramGroup` 全5件PASS、Podman 4.9.3/socket active、Docker engine/Compose未導入を実測。旧 `kb-system` はMasterにより放棄済みで再利用対象外。正式Dev KBは [gace-dev-kb](https://github.com/seigo-gace/gace-dev-kb) の正本、F:は原本保護。
- **2026-10-27の変化:** VS Code WSLとContabo SSHの接続回復およびCodex拡張旧版 `26.1007.21434` のインストール・接続復旧はMasterから報告されたが、**Codexジョブ実行許可を意味しない**。当日Windows経由のWSL検査は`WSL=OK`/`GSERVER_FILES=OK`ながら`GSERVER_HTTP=000`（localhost試作が応答せず）。このため10/23のHTTP200を現在の稼働PASSとして引用しない。
- **未確認:** 10/23にDocker Engine/Composeのインストール一括コマンドを提示したが、**実行結果は届いていない**。現在のDocker/server/container、8765、G:/F:mount、site_total/Redis/aaPanel、Telegram5リンクは**PCの10/27限定Read-only再測定待ち**。PCソースをGitHubにImportした証拠なし。KB検索/MVS/ACTIVE/rollback、TGSログ/暗号backup/download/隔離restore、Web/UI/API/Storage実機E2E、GitHub切断E2Eは未完成/未検証。
- **NEXT:** 10/27のPCでDocker/Compose実在・既存サービス/マウントと試作APIだけを一度で確認し、該当するS2-01/S2-02の未達を埋める。再びBot統廃合や放棄KBを調査しない。Docker/Compose-first・増設Server共通運用・Contaboを別Hostとして保護する本来のF01～F08は維持する。無許可のCodex/ServerAI委任や定期タスクは行わない。

## 2026-10-27 Docker/Compose導入ユニット｜Source完了・PC実行待ち

- Master PC最新 readback（`ACTION=PC_S2_RESUME_RUNTIME_READONLY`）: `VERIFY=PASS`; Docker Engine/Compose CLI/packageなし、Podman4.9.3/socket active、Redis/site_total/btpanel active、G: mounted、F:はWSL未マウント、Telegram参照リンク5/5、Source SHA一致、試作8765は`URLError`。これによりS2-02のDocker導入が未完了と再確定。
- GitHub実装 [commit `56b3b87`](https://github.com/seigo-gace/G-ACEserver/commit/56b3b87a8f23b53bd0039ac936acd6452f637118): `scripts/install_wsl_docker_compose.sh` と `tests/test_docker_bootstrap_contract.py`。Ubuntu24.04/WSL/SHAの前提、Docker公式鍵fingerprint、既存APTパッケージ削除防止のsimulation、Docker/Compose導入、`network_mode:none`一時smoke、Podman/Redis/site_totalの事後状態確認を実コード化。**ローカルbash構文と静的契約7/7 PASS**だが実機導入とSmokeは **NOT_RUN**。
- Master PCへの導入は、このコミットに固定したSHAを検証する1回実行のWSLコマンドで行う。Docker group付与なし、Contabo/TGS/Telegram/旧kb-systemへの変更なし。新規Docker Engine daemonはホストNetwork/Firewallへ作用し得るため、ポート公開を行わず、既存稼働と分離。Podmanを自動で削除しない。
- **NEXT（作業継続）:** MasterのWSL実機導入読戻し→S2のDocker/Compose環境での既存Gserver sourceの互換化・非破壊コンテナ化→S3 Storage/Web、S4正式Dev KB、S5 TGS送受信+隔離復元、S6/S7運用・全受入の実装。インストール成功だけでF01～F08の完成とはしない。

## 2026-10-27 Docker host verified; isolated existing-source staging prepared

- **HOST VERIFIED:** Master PC (2026-10-27) `ACTION=WSL_DOCKER_COMPOSE_BOOTSTRAP` `VERIFY=PASS`, Docker daemon `29.9.2`, Compose `v5.6.1`, official signing fingerprint verified, apt install count 7/remove count 0, isolated `hello-world` Compose smoke PASS, no published ports. Podman socket, Redis and site_total remain active. This completes only **GSR-S2-02 runtime bootstrap/smoke**, not app containerization or Gserver F01–F08.
- **STAGING IMPLEMENTATION:** [commit `33c79ab`](https://github.com/seigo-gace/G-ACEserver/commit/33c79abc301488369edbc69b7bea2d6884cf6f4d) introduced `deploy/compose.gserver.staging.yaml`, `scripts/smoke_gserver_staging.sh`, `tests/test_gserver_staging_contract.py` (7 static checks; not claimed as executed CI). Does **not copy/modify** old Python source; bind-mounts only `/mnt/g/Project/Gserver/app/gserver.py` read-only with SHA256 guard. Isolated `network_mode:none`, no host port or access to G:/F: data, nonroot / all capabilities dropped, limited resources, healthcheck only localhost:8765; any old 8765 process untouched. Staging project is guarded against name reuse and shut down afterward.
- **STAGING HOST EVIDENCE:** `NOT_RUN` until Master executes pinned snapshot of compose+script on WSL. Image `python:3.12-slim-bookworm` is a mutable tag **only for one-off staging**; pin digest and build actual app runtime / data volumes after source dependencies are confirmed. Existing source may require root path/config; failure of isolated healthcheck means compatibility needs work, not that Gserver data is destroyed.
- **NEXT:** Run pinned read-only staging test on PC, inspect only the bounded failure evidence if no 200; adapt / package existing app without altering original; implement persistent Compose service, authorized G: data mounts, existing Dev KB, TGS ZIP/receipt/readback/isolated recovery, then S7 E2E. The entire Gserver Mission is still open.

## 2026-10-27 isolated staging FileHandler /logs runtime repair

- Master WSL reported `unittest 9/9 PASS` and isolated container `exited (1)`, with bounded pre-cleanup traceback locating the failure to existing `app/gserver.py:22` `logging.FileHandler(LOG_PATH)`: `FileNotFoundError: '/logs/gserver.log'`. Stage `STAGING_HEALTH_FAILED`, diagnostic readback succeeded, temporary container successfully removed. This is **a missing writable staging log directory**; do not label Docker Engine/Compose failed or the Gserver app production-ready.
- Source fix [commit `7b3538a`](https://github.com/seigo-gace/G-ACEserver/commit/7b3538a0317628a887108828a2ac15ee9ae2087b) mounts a **private ephemeral tmpfs** at `/logs` (UID/GID 65534, 0700, 16 MiB, noexec/nosuid/nodev), leaving host logs and G: data unaffected; staging adds assertion that the existing Python FileHandler created `/logs/gserver.log`. Test case added for private tmpfs, with log verification guard in [commit `b033a12`](https://github.com/seigo-gace/G-ACEserver/commit/b033a1293c3cf45bedf7749cf49b34e04adbccdf). New static source guard assertions 10/10 agree with saved scripts/configs, but **10 actual Python unittests and WSL staging smoke are NOT YET RUN**.
- **NEXT:** Execute pinned+blob-verified revision `b033a1293c3cf45bedf7749cf49b34e04adbccdf` on PC for 10 static tests + isolated runtime HTTP200 + ephemeral log file existence + teardown. On success, proceed to real Gserver service packaging, **persistent production logs/data volumes** and service health/restart/port design under S2; then S3 storage, S4 official Dev KB, S5 TGS, S6/S7 acceptance. Never retain staging tmpfs as production log storage.

## 次の実装単位
2026-10-23のWSL実機読戻しで旧Gserver試作（109行、SHA256=41e0df51db854fd562f748b4f8dbcc558d0052d2d52d2957f6d3a89b9f61e15c）のsource内容、localhost HTTP200、PID/port所有、既存Web/Redisの一部稼働を確認済み。Windows F:のG-ACE-KB関連既存フォルダも存在確認済み。**一方、正式Dev KB検索E2E、GserverのF01-F08全機能、TGS復元は未確認。** 旧kb-systemは放棄済みで再利用対象外。

**NEXT：GSR-S2-01** — 既存Gserver試作とWeb入口、Linux実行配置、F:/G:データの責務と非破壊移行・差戻しを確定し、S2-02以降の必要実装へつなぐ。Telegram関連5資産は一つの保留グループとして扱い、移動・再利用判断は別作業に切り分ける。**これをGserver開発の停止条件にしない。**

## 作業判断の権限
Master：最終目的／優先順位／不可逆影響／限定Server AI投入判断。
ChatGPT：既存ルール #17に従う計画/証拠の調整。
PC-Codex：既存ルール #16に従う指定タスクの最小実行。
GitHub現行Issueが実行状態、Notionは会議・歴史の参照。実機/元RepoがSourceとRuntimeの一次証拠。

## 実装済みの誤認禁止
ドキュメントとタスク移行は実Web/Bot/KB/TGSのコード導入・Windowsでの稼働証明・外部公開・DR復旧の完了ではない。
タスク完了証拠：TASK_ID、対象OS/Repo、Source path/SHA、変更diff、依存/競合、test exit、PC Runtime、TGS readback、rollback、NEXTをIssueへ記録する。

## GitHub管理の実際の再開入口
- [CURRENT Issue #9](https://github.com/seigo-gace/G-ACEserver/issues/9)を新チャット/PC Codexの入口とする。
- Stage Issues [S0 #1](https://github.com/seigo-gace/G-ACEserver/issues/1)から[S7 #8](https://github.com/seigo-gace/G-ACEserver/issues/8)へ、46タスクをチェック項目として登録済み。
- GitHub Project #1へのProjects v2項目追加は未検証。Project登録済みと誤記禁止。
