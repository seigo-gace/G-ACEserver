# Gserver全体構造｜ターゲット
**論理設計。実PCの現行FileTree/稼働証拠ではない。**

```text
Windows PC Host (起動・電源・Firewall・VS Code)
└─ WSL Ubuntu (D:上のLinux仮想ディスク)
   ├─ 既存Web入口 nginx / aaPanel ? → Web UI / API
   ├─ Bot (サービスごとに分離)
   ├─ Storage adapter → G: (データ・local backup)
   ├─ G-ACE Development KB (既存 mcp-vector-search)
   │   ├─ Gitコミット由来の開発履歴
   │   └─ ModuleCatalog受領→ACCEPTED→索引→単一Current ACTIVE→MCP/Deep health
   ├─ TGS送信/検索クライアント → 有界spool → 既存TGserver（別VPS）
   ├─ Backup: 整合性snapshot→暗号化→分割→TGS保存→取得→復元
   └─ systemd/OS防御/必要最小OSS監視
F: = KB移行元（切替完了・復元実証まで維持）
```

## コンポーネント単位の責務
Web公開はまず既存nginx/aaPanel設定を読取り、Python HTTP試作との重複を解消。KB検索エンジンは新規作成しない。TGSは通知Botの新設ではなく既存ZERO/vNextと実APIを照合。WindowsとWSLのランタイムは互換バイナリと誤認せず必要なOS版を選び、Windowsで使わないものだけ整理する。
監視はOS標準と既存Webから開始し、CrowdSec（防御候補）、Beszel（リソース監視候補）、Uptime Kuma（死活監視候補）から不足機能に適合する最小部品のみ採用。どれも未導入候補であり、導入済みとしない。
`docs/tasks`に46単位の実行計画、`docs/architecture/CONFLICTS.md`に衝突台帳、`docs/architecture/TRACEABILITY.md`に要求追跡を置く。

## ファイル配置方針
コード/venv/状態DBはLinux FS候補、G:は大容量データ、F:は原本。旧G:試験コードと提案されたLinux配置の実一致は不明なのでS1で現物確認後にFileTreeを確定。実行プロセス・port・秘密値は公開Repoへ記載しない。
