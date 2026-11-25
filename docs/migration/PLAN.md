# CodeLens migration blueprint

Baseline source: main at f525097. This plan describes prospective behavior. Each numbered phase requires a new explicit instruction. After a restart, compare this plan, STATE.json, DECISIONS.md, the working tree and the latest user authorization before editing.

## Product boundary

Install one local Python distribution. A command, a Textual action and an MCP tool each call the same application services. A session selects the evidence for every read and write. Opening a second session may reuse indexed data while starting an empty conversation.

    CLI / TUI / stdio tools → application services → SQLite store
                                      │
                            ingest / retrieve / build context
                                      │
                         standalone generation only → provider

Keep the Next.js frontend, FastAPI routes, admin settings, PostgreSQL/Alembic, Docker contexts and deployment paths independently runnable. Use the sidebar's section IDs and the eight prompts' subject matter as the compatibility contract. Adapt the prompts for citations, coverage and budgets. Reuse the ignore/size lists as starting inputs, subject to traversal tests. The hosted ORM, GitHub clone helper, OpenAI configuration singleton and embedding pipeline depend on hosted infrastructure. Importing the hosted database module alone constructs an engine. The package gets its own composition root and migration history.

## Checkout findings

| Issue | Evidence under backend/app | Replacement and regression gate |
|---|---|---|
| 1. Context omits source | services/analysis_service.py, _build_project_summary formats up to 500 paths, extensions and sizes for every prompt | P2 select different cited passages for routes, models and architecture; assert request contents |
| 2. Chunk vectors overwrite | services/embedding_service.py, generate_and_store_embeddings updates the same file ID inside the chunk loop | P1 persist one searchable row per chunk. Any future dense index keys vectors per chunk and model |
| 3. Wrong passage returned | search_similar ranks files and slices content[:2000]; index_files also truncates at 50,000 characters | P1 place unique text near EOF, verify exact lines from stored bytes |
| 4. Stale reuse | services/repository_service.py, find_by_owner_repo prefers completed rows using owner/name alone | P1 store ref resolution, manifest and settings; test dirty and untracked edits |
| 5. History outlives evidence | reset_for_reanalysis deletes analysis/files; api/routes.py reads chat by repository_id | P1 pin session snapshot; P2 pin artifact versions and test chat survives refresh |
| 6. Failure looks successful | _generate_section returns generic exceptions as text; analyze_repository stores all sections together and marks completed | P2 inject a failure after a completed section and verify retry skips that success |
| 7. Ignore traversal | _walk_directory continues on a directory yielded by rglob, which still visits descendants; node_modules children can enter the index and ignored files count toward limits | P1 prune before descent, check nested exclusions before accounting |
| 8. Clone credential exposure | clone_repository interpolates optional token in URL, logs it on success and includes Git exceptions on failure | P1 use anonymous public fetch with sanitized errors; test redaction. Hosted path remains exposed pending a separately scoped demo fix |

The hosted pipeline explicitly sequences clone, index, embed and eight completions. Sidebar.tsx lists overview, architecture, folders, api, database, diagram, readme, suggestions and chat. The legacy deployment_summary and dependencies fields receive empty values. Folder Explorer also needs a deterministic source tree.

## Package layout and dependencies

Root pyproject.toml with setuptools, explicit src package discovery, packaged SQL migrations/prompts and a project.scripts entry for codelens. Keep backend/pyproject.toml scoped to hosted tests. Proposed modules under src/codelens:

| Module | Ownership |
|---|---|
| domain | IDs, section names, line ranges, status and typed errors |
| application | Repository/session use cases, network policy, generation, export |
| ingestion | Local discovery, public Git fetch, manifest and coverage |
| retrieval | Line-preserving chunker, lexical search, evidence budget |
| persistence | SQLite connection policy, queries, ordered SQL migrations |
| providers | Lazy OpenAI, Ollama, Anthropic and compatible adapters |
| adapters | cli, tui, mcp entry points and presentation |
| prompts | Versioned per-section templates and evidence instructions |

Core needs Typer, platformdirs, stdlib sqlite3 and Git for Git inputs. Use optional tui, mcp and provider extras. Use a lightweight streaming HTTP client for Ollama. No dense index in the initial plan. Start compatibility testing with Python 3.12 (checkout pin 3.12.8) and 3.13 (existing backend environment). Establish lower bounds by clean installation and entry-point tests in each owning phase. Record supported versions only after those tests. Verify the official MCP SDK's stable release branch when Phase 3 begins.

## Persistence contract

Opaque IDs in public interfaces. Use UTC timestamps. Proposed tables by first owning phase:

| Phase | Table | Principal fields and constraints |
|---|---|---|
| 1 | repository | id, kind, canonical_source, unique(kind, canonical_source) |
| 1 | snapshot | id, repository_id FK, commit_sha nullable, manifest_digest, settings_json, ingestion_version, created_at; unique repository + revision + manifest + settings/version using a non-null normalized revision key |
| 1 | blob, file | SHA-256 PK and exact bytes; file ID, snapshot FK, normalized relative path, blob FK, byte/line counts, encoding, coverage/reason; unique(snapshot,path) |
| 1 | chunk | id, file FK, ordinal, line_start/end inclusive, exact text, hash, chunker version; unique(file,version,ordinal); derivative FTS rows keyed by chunk ID |
| 1 | session | id, snapshot FK, requested ref, created_at, optional parent session; many sessions per snapshot |
| 2 | message | id, session FK, sequence, role, content, origin, timestamps, status, request ID; unique(session,sequence) |
| 2 | artifact | id, snapshot FK, section, version, format, body, status, request/cache key, evidence digest, prompt/provider/model/settings, origin, timestamps |
| 2 | evidence, session_artifact | ordered artifact or message citations to snapshot file and inclusive lines; session/section/version links preserve the artifact selected at each generation |
| 2–3 | job, request_receipt | session/snapshot FK, request ID and payload digest, operation, attempt, checkpoint, lease, status, safe error, optional usage; unique client/request scope; committed record IDs for replay |

Enforce snapshot equality with composite foreign keys or checked joins inside the write transaction. Validate path membership and line ranges against stored files. Allocate message order within a short write transaction. Use constraints to arbitrate racing opens and idempotent saves; same request ID with changed payload is a conflict. Publish completed artifacts and session links atomically. Lease expiry makes abandoned jobs resumable. Checkpoint partial text under a distinct status; completed cache lookup selects only successful versions.

Migrate incrementally under a bounded writer lock, with a schema version updated in the same transaction. Enable foreign_keys per connection, bounded busy_timeout, WAL where supported. Reject newer unknown schemas with recovery guidance. Back up existing stores using SQLite's backup API before upgrades, verify integrity and rehearse restore. Keep blobs and authoritative chunk text in the database, so deletion of the cache cannot remove history. Stage bounded input outside write locks and publish a whole snapshot atomically. No network wait while holding a write transaction.

## Concrete Phase 1 sequence

1. Establish root packaging, command groups, isolated test homes and lazy composition. Resolve data/config/cache via platformdirs; CODELENS_HOME redirects all three beneath one root. Doctor reports paths, schema compatibility, Git and runtime FTS probe without contacting services.
2. Implement first migration and repository/snapshot/session queries. Use private user storage permissions. List/resume resolve IDs directly without consulting the source or loading any generation plugin.
3. For a Git worktree enumerate tracked and nonignored untracked paths with git ls-files -z --cached --others --exclude-standard, scoped to the selected directory. Read eligible working-tree bytes once, including dirty changes; omit deleted paths. In plain directories prune VCS, dependency, build and hidden directories top-down; document built-in rules and that Git ignore semantics require a worktree. Apply hard exclusions to both modes, including .env files, key material, links, devices, nested repositories and CodeLens storage. Never follow symlinks on open. Record size/encoding/coverage and enforce file, byte and operation limits. Fail clearly if enumeration becomes inconsistent.
4. Canonicalize public github.com owner/repository HTTPS inputs, reject credentials, unsafe refs and alternate transports. Use isolated temporary Git storage with prompting, credential helpers, ambient URL rewrites, hooks, submodules and external filters disabled. Fetch the requested branch/tag/commit (default remote HEAD), resolve exact SHA and read its tree. Bound time and transfer/storage; clean up on failure. Test ref resolution with controlled Git fixtures at the transport boundary plus a public smoke when available.
5. Hash sorted length-delimited paths, content hashes and coverage with the ingestion/ignore policy. Key indexes by snapshot and parser/chunker settings. Preserve exact bytes, define UTF-8 text eligibility and line handling (CRLF, final unterminated line, empty file and oversize line tests). Store exact chunk passages and order BM25 hits by ascending score then stable ID. Parameterize and quote user tokens. Apply snapshot filtering before limit. Without FTS5, report how to install a Python SQLite build with FTS5; exact path reads and history still work.
6. Wire open, list/resume, search, source, refresh and doctor. Enforce offline at the application service boundary before any transport or subprocess fetch. Strict offline blocks all inference including loopback, downloads and remote Git; local Git metadata and stored reads remain available. A changed refresh creates a new session on the new snapshot, leaving the original session addressable. Unchanged refresh returns the existing pair. Plain open always creates an independent session.
7. Install in a clean venv. Exercise real commands across processes against a disposable worktree with late-file marker, ignored files and two sessions. Delete/move the original after refresh. Verify both versions and session isolation with network denied. Race two opens, inject interrupted capture, missing FTS and busy writers, and verify FK/integrity checks.

### Phase 1 implementation record

The installed commands and limits are documented in the root README. Phase 1 uses anonymous GitHub commit resolution and a bounded archive reader in place of a temporary clone, per-directory Git ignore checks during descriptor-relative traversal, and a bounded scan as the FTS5 fallback. The implemented schema is version 1 in src/codelens/persistence.py. Snapshot policy carries the chunker version for all of its chunks. Verification uses an installed package: `python -m pip install . pytest`, then `python -m pytest -q tests/local`. STATE.json records the environment and observed results.

## Command contract

All identifiers below are opaque. Commands support --help. Machine-readable commands offer --json (one result on stdout, diagnostics on stderr). Plan exit 0 for success, 2 for usage, 3 for missing records, 4 for policy/configuration, 1 for other failures and 130 for interruption. Offline is available at the command position shown by the user. Stored reads always use the offline-safe path.

| Invocation after codelens | Result |
|---|---|
| open SOURCE [--ref REF] | repository, immutable snapshot and fresh session IDs; ref applies to remote inputs |
| sessions list / sessions resume SESSION --offline | paged sessions / saved snapshot, messages and linked artifact versions |
| search SESSION QUERY / source SESSION PATH --start N --end M | ranked passages / exact bounded stored lines |
| refresh SESSION | changed flag, old/new snapshot and session IDs |
| doctor | local diagnostic results and actionable remedies |
| setup --provider NAME --model ID | user settings; noninteractive options and environment/keyring secret lookup |
| analyze SESSION --section NAME or --all | completed independent sections, cached/retried status and IDs; explicit regeneration creates a version |
| ask SESSION QUESTION | stream answer, save ordered turns and citations; JSON mode emits final structured result |
| show SESSION SECTION --offline | exact linked saved content, with explicit version selection |
| export SESSION --format markdown/json/mermaid | deterministic saved data, raw diagram for mermaid, explicit output destination |
| tui / mcp serve | terminal app / local stdio server |

## Phase 2 implementation record

Install the root distribution and run `python -m pytest -q tests/local tests/generation`. The standalone section, chat and export commands use schema v2. `context.py` builds bounded requests, `providers.py` reads streaming protocols, `generation.py` checkpoints attempts, and `records.py` projects saved outputs. The README documents model selection, cache/retry semantics and export formats. Tests cover CLI restarts, guarded offline reads, interrupted/failed streams and v1 migration. A separate loopback HTTP fixture exercised streaming before completion. The user manually verified one live OpenAI overview generation. Live Ollama inference remains unverified.

## Generation and tools

Application provider interface: stream(request, cancellation) yields text deltas, optional usage and one terminal event, or a typed auth, connectivity, rate-limit, unsupported-feature or provider error. Request includes explicit model, ordered dialogue, section instructions, cited passages, deadline and output budget. Adapters advertise capabilities, close streams on cancellation and preserve unknown usage as null. Bound retries before first output; after partial output retain the attempt and require explicit retry. Store user turn/request before generation and checkpoint assistant text. Credentials stay in environment/keyring. Treat source as quoted untrusted data. Cloud providers and hosts receive the selected context and can retain their own history.

Route/schema samples for api, models/migrations for database, entry points/imports/services/config/deployment for architecture and diagram, directory samples for folders, manifests/docs/entry points for overview and readme, targeted source/test pairs for suggestions. Budget context after reserving instructions, dialogue and output; label omissions, inference and insufficient evidence. Validate citations before accepting completion. Cache on snapshot, section, ordered evidence hashes/ranges, prompt version, provider/endpoint identity, model and relevant settings. Optional future embeddings require chunk hash, model revision and dimensions. Prefer explicit replay of saved answers. Any automatic answer key must include the selected conversation context.

MCP contracts below share the same store. The session pins the snapshot. Require explicit snapshot ID on source/context reads and evidence-bearing writes. Validate both together. Clamp limits (initial target 50 items, 200 lines and 32 KiB per read), return truncation indicators and opaque stable cursors.

| Tool | Inputs → result |
|---|---|
| open_repository | source, optional ref, request_id → IDs or bounded job handle |
| refresh_repository | session_id, expected snapshot_id, request_id → refresh result or job handle |
| search_code | session_id, snapshot_id, query, cursor/limit → hits with paths, lines and chunk IDs |
| read_source | session_id, snapshot_id, path, range → exact stored passage and continuation |
| get_context | session_id, snapshot_id, purpose/query, budget → cited excerpts, coverage |
| list_sessions / read_session | cursor/limit / session_id and cursor/limit → IDs, history, links and job checkpoints |
| read_artifact | session_id, artifact_id, cursor/limit → linked version, origin, body |
| save_artifact | session_id, snapshot_id, section, format, content, evidence, host provenance, request_id → committed receipt |
| record_exchange | session_id, snapshot_id, submitted turns, evidence, host provenance, request_id → committed ordered message IDs |

Host reads saved artifacts, retrieves evidence as needed, generates using its own authentication, explicitly submits output and claims persistence only after a receipt. Store tool events and explicit submissions. A host transcript requires separate opt-in client integration. Keep protocol stdout clean. Use bounded job steps with persisted checkpoints and status via read_session; core tools require neither sampling nor special host extensions.

## Phase gates and prospective verification commands

Run hosted baselines alongside each phase. Proposed tests below are future files. Use controlled fixtures, fresh processes, isolated homes and forbidden network/provider spies on read paths. Report live interoperability separately.

| Phase | Deliverable and acceptance | Verification from repository root |
|---|---|---|
| 0 | Inspect checkout, verify issues, baseline existing demo and validate migration records | See STATE.json |
| 1 | Install package, capture/search/refresh and prove correct late-file lines, immutable evidence, independent offline sessions | python -m pip install -e . ; python -m pytest tests/local ; codelens doctor |
| 2 | OpenAI/Ollama, all eight sections, chat, streaming, retries, export. Compare saved bytes after restart, credentials removed, provider switched and network blocked; cancel one section and reuse completed siblings | python -m pytest tests/generation ; codelens analyze SESSION --all ; codelens show SESSION api --offline |
| 3 | Real SDK client launches stdio subprocess, discovers tools, saves twice with same key, races CLI writer, restarts, reads identical saved content via CLI; validate Claude Code/Codex configuration and record available live-host results | python -m pytest tests/mcp ; codelens mcp serve |
| 4 | Textual picker, tree, search, eight sections, stream/cancel/recover, indicators, offline and partial states, export and raw Mermaid. Pilot exercises arrows/Enter/Tab/Escape, palette and session switching; manual terminal smoke | python -m pytest tests/tui ; codelens tui |
| 5 | Anthropic and compatible endpoint capabilities, core-only install, package data, tested OS/Python matrix, upgrade backup and restore, terminal/secret boundaries, CI and user docs. Assess legacy import with unknown provenance and no credentials. Check name availability and license rights before publication | python -m build ; python -m twine check dist/* ; install wheel and sdist in separate clean envs outside checkout; rerun all acceptance paths |

Publication, release creation and deployment require separate authorization. No tracked license file was identified at baseline.
