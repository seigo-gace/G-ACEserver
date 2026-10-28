# F04 — Existing G-ACE Dev KB Current bridge

## Authority and implementation

The authoritative KB remains seigo-gace/gace-dev-kb with mcp-vector-search 4.1.14 (BM25, Vector, Hybrid, Knowledge Graph, MCP). Gserver does not reimplement indexing, the receiver, activation, Current or rollback.

- app/kb_source.py: reads the existing F:/G-ACE-KB (WSL /mnt/f/G-ACE-KB) ACTIVE marker, runtime-state and receipt. Requires the same 40-character commit, schema v2, ACTIVE status, matching six SHA256 declarations and valid counts.
- scripts/gserver_kb.py: owner-only WSL CLI for inspecting the F: Current. The default mode reads only authority JSON and existence indicators; --verify-hashes checks six source files; --verify-projection calls the installed KB's original Python byte-exact runtime projection verifier, only when hash checks pass.
- tests/test_kb_source.py: fixture-based tests for consistent/absent Current, tampering, uncommitted transaction, unsafe symlinks, missing original verifier, timeout and non-mutation.

## Status meanings

| Status | Confirmed | Not confirmed |
| --- | --- | --- |
| NOT_ACTIVATED_OR_NOT_FOUND | No generalized Current marker; historic baseline may exist | Search/current activation |
| ACTIVE_AUTHORITY_CONSISTENT | Marker/state/receipt agree on identity/schema/hash claims | Actual file bytes or search |
| ACTIVE_AUTHORITY_HASHED | Six actual source bytes match agreed digests | Live Markdown projection or MCP retrieval |
| EXISTING_KB_VERIFIER_PASS | Original Dev KB accepted-to-live Markdown byte-exact projection verifier passed | MVS/BM25/Vector/Hybrid/KG/MCP runtime |
| KB_SEARCH_E2E=NOT_VERIFIED | No query was performed | F04 final acceptance |

## Security and deployment boundary

- Windows F: availability and WSL /mnt/f are separate facts. `scripts/gserver_kb_mount_probe.py` inspects the exact /proc/self/mountinfo mountpoint and known KB markers without auto-mounting or moving files. If F: is missing, do not fabricate activation or try alternate drives.
- An authenticated Gserver `GET /kb` status route is source-implemented. It requires an explicit `GSERVER_KB_ROOT` and `os.path.ismount` for that KB root in the container, returns only a bounded status and existing KB presence flags, does not expose knowledge, hashes or paths, and returns 503 on missing/invalid KB. It does not rebuild the search engine or imply BM25/Vector/MCP search readiness. The default container has no F: bind mount or KB root option, so this route remains unavailable until deliberate isolated deployment.
- The CLI is read-only. It does not modify F:, G:, Docker, Windows tasks, firewall, GitHub, KB acceptance, MVS indexes or Current. It adds no network API, token, automated agent or new search engine.
- Default F: access fails closed when /mnt/f is not mounted. All inspected paths are fixed within the configured root; symlinks and non-regular authority files are rejected. Authority JSON is limited to 256KiB; deep hashes stream bounded data, capped at 2GiB per file.
- The existing Windows KB health PowerShell command creates a receive lock and intake path, so it is not invoked automatically by this bridge. The optional projection check reuses only the original read-only Python byte-exact projection verifier and never emits KB content.
- A PREPARED transaction journal blocks acceptance. A mutable Current is rechecked after validation; successful hash/authority checks are not equivalent to a live MCP query.
- Some generalized ModuleCatalog features remain on an unmerged Dev KB feature branch. This adapter does not claim they are installed on the actual PC.
- No F: to G: move or KB rebuild occurs. Migration requires source identity, full data/index inventory, transfer/hash proof, and independent rollback acceptance.

## Master PC read-only acceptance

From the existing Gserver WSL repository: run Python test_kb_source.py and scripts/gserver_kb.py after clean git pull. Only if an ACTIVE snapshot is proven, --verify-hashes --verify-projection may be used for deeper read-only validation. Missing original KB runtime means the correct outcome is NOT_VERIFIED or a clear error, never a fabricated PASS.

## Excluded tasks

The Master cancelled wife-PC, LAN SMB, related VPN/proxy and firewall work. Existing LAN-Inbox is left untouched. F03 isolated real G: reversible storage readback has separately passed; that is not F04 acceptance.