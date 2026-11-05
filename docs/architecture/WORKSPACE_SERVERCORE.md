# Gserver Workspace / server-core統合（2026-10-31 Master追加委任）

## 目的と正本

Gserverでもserver-coreを司令室とするWorkspaceで開発全体を扱い、既存ServerTerminalからContaboとGserverを区別して操作できるようにする。GitHub Project #1、server-core Rule Plane、Current/実行/結果/復元の既存Agent Loopを再利用する。独立した指令室、Gateway clone、Rule全文の複製、新規常駐AIは作らない。

正本はG-ACE-inc/server-coreのREADME / LOAD_SCOPE / Rule Plane Manifest / #16 / Control #10 / CU #40。Gserverの所有CurrentはIssue #9、実装branchは既存Draft PR #15。最新の継続設計はControl #10の[2026-10-31引継ぎ](https://github.com/G-ACE-inc/server-core/issues/10#issuecomment-6535887127)と[依存確認順](https://github.com/G-ACE-inc/server-core/issues/10#issuecomment-6536859483)。この追加委任は従来の「Contabo不使用」を当該統合の調査範囲に限って更新する。他Project/本番Providerの変更権限へ拡大しない。

## 採用する構成

- Gserver WSLのlocal server-core checkoutは同一upstream正本の取得物とし、別fork/別Rule Plane/独立Terminalへしない。VPSのcheckoutは既存稼働のまま維持する。
- Workspaceはserver-coreを先頭、既存Projects rootを次に配置する。既存Gserver/他Project/原本を移動しない。shared helperのexpected_workspaceを再利用し、既存Source/CI、除外設定、model/cost選択を維持する。
- local adapterは入口とHost path対応だけを持つ。VPSのcanonical_host_rootをWSLへ機械的に書換えて実行権限を作らない。SERVER_AIは#16、GPT CHATは既存#17/Agent Loopを、それぞれの実行面で使う。Codexの実行にCHATの会話/Notion手順を混入しない。
- Contabo操作は既存server-core→Actions→Gateway→Receiver→Host Writer→Result Sinkへroutingする。Gserver自身の遠隔操作には別targetとPC側Receiver/Writerが必要。Control #10のregistryにWSL pathを追加するだけではPCへ届かない。
- remote requestはHost target、dispatcher SHA、target repo SHA、command SHA、request/Run/resultを照合する。既存の重複排除、認証、時間/出力制限、Secret非表示を維持。ReceiverへDocker socket/rootを与えない。Sourceの登録や202は実Host実行の証拠ではない。
- ローカルCore/Storage/独立appの通常起動はGitHub/Contabo/Terminalに依存させない。PC offlineはoffline/retryとし、無断wake、WAN fallback、他Hostへの誤配送をしない。

## 優先順位と継続

1. 既存の正常Core/Storage/VPNを維持し、Workspace入口を独立して構築・検証する。Native clientの実際のRule読込はファイル検査と別Gate。
2. VPN/Cloudflareの正式認証・G-ACE所有zone・到達性を確認する。
3. Control #10の既定順序で、P015既存Topic/Repo map/runtime → Gateway正式API/専用認証/destination/dataPolicy → Vault既存consumer/credential注入 → PC Producer→P015→Readerの相関E2E。
4. 同じ共通TerminalのGserver target/Receiver/Writer/Sinkを既存Sourceから移植・設定する。提供元への必要な差分は元CU/Ownerと調整し、共有VPS稼働は不用意に変更しない。
5. GitHub→Gserver→結果の一往復、Contabo回帰、誤SHA/認証/二重配送/offline、Secret非露出、既存container不変、復旧/rollbackを実証する。

## 受入

Workspace配置/入口、GitHub Project Current復元、実client Rule読込、Contaboの既存経路、Gserverの実行経路、ループの実継続、失敗/電源断復旧を個別判定する。Source/単体テストだけで移植完了とはしない。既存F01〜F08/46タスクは縮小せず、本追加要件と並行して継続する。

## Local adapterとrollback

`scripts/gserver_workspace.py`は既存checkoutのorigin/clean tracked Source/必須authority/Rule #16分離を照合し、所有Repoの`expected_workspace`をそのまま利用する。既定は読取検証のみ。明示`--install`でlocal workspace JSONと既存Projects rootの最小AGENTS/Cursor path adapterだけを作成する。既存内容との衝突は全file事前確認で拒否し、別のCursor設定、model、MCP、tokenを上書き/作成しない。途中失敗は自分が作った同一inodeのfileだけを戻し、並行置換を消さない。利用者が後から設定を変えた場合も自動上書きせず差分確認を要求する。

rootはCLIで既存local pathを指定可能。生成物の実パスやHost inventoryは公開Sourceへ保存しない。最初のinstallは生成した4fileだけを対象とし、rollbackでは現在内容を照合してその4fileだけを外す。upstream checkoutを自動削除せず、元Gserver・G:原本を移動しない。

2026-10-31 local実測: 同一upstream main c688961d29a7485c9a4d949a95c1991a452c7ec8を取得し、生成Workspaceのserver-core先頭/既存Projects参照/4fileの内容読戻しPASS。取得物にtracked差分なし。これはSource/配置の実測であり、Cursor/VS Codeを再接続して実Rule loadingを観測したものではない。VPS操作やGserver遠隔コマンド、Agent Loopの実継続も未受入。

補足: upstream server-core自体のCursor bootstrapにもVPS絶対pathがあるため、local checkout内へ追跡対象外の最小path adapterを追加する。元のtracked Ruleを編集せず、local authority読込だけを同folderへ対応付ける。実VPSの実行root/認証/Host選択は変更しない。配置したことだけでnative Active Rulesを読込済みと判定しない。
