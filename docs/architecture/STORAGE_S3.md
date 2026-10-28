# S3 read-only storage implementation

Tasks advanced: GSR-S3-01/02/04 (partial). F03/F06/F07 gates remain open.

`app/storage.py` extends the existing Gserver capacity API with an explicitly configured subtree capability. `GSERVER_STORAGE_ROOT` identifies the mount; `GSERVER_FILES_ROOT` must be a strict child of it. The default files root is absent, so file APIs return 503 and no original data is exposed. Base Compose does not mount G:/F: or inject credentials. Actual mount/ingress/credential configuration remains a separate protected deployment action.

Authenticated endpoints:

- `GET /files?path=…&after=…&limit=…`: lexicographically ordered pages, maximum 200 entries; scans at most 10,000 directory entries and fails rather than silently claiming completeness above that bound.
- `GET /download?path=…`: regular files only, 64 KiB streaming chunks, attachment disposition, ETag and single HTTP byte ranges (206/416). A changed If-Range validator falls back to a full response.
- `/storage` and `/mounts`: existing capacity response with missing-mount protection.

Paths are relative, with absolute paths, dot traversal, NUL, backslashes, Windows device aliases, alternate data streams and trailing dot/space ambiguity rejected. Each directory/file is opened relative to an already opened directory descriptor with `O_NOFOLLOW`. Nested mounts, hardlinks, symlinks and special files are excluded. The process remembers the mount device/inode identity and refuses a replacement. The files subtree may not be the entire drive. This is not proof of physical USB identity or Windows NTFS semantics; those remain real-device acceptance items.

No write, rename, delete, upload, index or backup operations are exposed. Missing/disconnected storage fails closed. Interrupted downloads close the connection and do not claim a complete response. The API does not promise a point-in-time snapshot of concurrently modified source files. Directory cursors are names, not durable snapshot cursors; concurrent changes can require refreshing the list.

The UI provides folder navigation, refresh, next page and save actions. Supported browsers stream into a user-selected file; the fallback is bounded to 16 MiB and cancels if a file grows beyond the limit. Credentials remain in memory and are never put in URLs or persistent browser storage. Logout cancels active transfers and invalidates stale responses. File names are rendered as text. HTTP responses and sanitized audit events share `X-Request-ID`/`event_id`; request paths, queries and credentials are not logged.

Verification uses temporary synthetic files only: directory pages, path/Windows alias attacks, symbolic/hard links, FIFO refusal, missing/replaced mount, three file sizes with SHA-256 equality, HTTP authorization/download/range/traversal, and four Node VM UI behavior checks. The tests mock mount presence and do not certify G:/USB or browser E2E.

Next S3 work: confirmed physical drive/subtree authorization, approved deployment with real read-only mount, actual browser/NTFS E2E; then reversible atomic upload/update/delete with quota and confirmation flows. Do not open destructive operations or close S3 based on the current read-only tests.

## 2026-10-28 local CLI host-side create-only transfers

The authenticated Gserver HTTP API remains **read-only**; the currently installed immutable Docker image is not changed. The new `scripts/gserver_files.py` provides local WSL-owner file transfers directly through the **existing** `/mnt/g/GserverStorage/files` mount, using the same storage capability boundary as listing/download. `put SOURCE_PATH` streams a regular local file into a create-only temporary file under the authorized subtree, fsyncs it, then publishes the destination via a same-directory hard link. A pre-existing name, symlink, or directory is never overwritten; ordinary errors clean up partial files. A SHA256 and size receipt are returned. `get NAME DEST_DIR` copies a file to an existing output directory, with no overwrite. `list` reads the existing bounded storage listing. No Docker rebuild, credential change, public network, or additional Host daemon is needed. Source file modifications during transfer are rejected. Transfer uses 1 MiB buffers rather than loading whole videos into memory.

The user-visible Windows folder is `G:\\GserverStorage\\files`. This initial CLI capability is **local to the WSL owner**, not LAN upload/share/HTTP write. NTFS/DrvFS support for the atomic hard-link publish operation and large-file transfer performance require real-PC verification; EOPNOTSUPP is an unverified possibility. There is no server-side resume yet. A forced kill or crash may leave a `.gserver-part-...` file, which must not be assumed complete; a later cleanup protocol is pending. The new local CLI has not yet been accepted on actual G: media as of commit `c5777a3`.
