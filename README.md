# CodeLens

**Understand Any Codebase in Minutes**

CodeLens is a production-ready AI-powered developer tool that analyzes public GitHub repositories and generates comprehensive documentation, architecture diagrams, API summaries, and intelligent Q&A using Retrieval Augmented Generation (RAG).

## Local repository browser

The standalone Python CLI captures a local directory or a public GitHub revision and lets you browse the saved source offline. Install from the checkout in a virtual environment (tested on Linux with Python 3.13):

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .
codelens doctor
codelens open . --json
# Or capture a remote branch, tag or full commit SHA:
codelens open https://github.com/octocat/Hello-World --ref master
```

Copy the returned session ID into the following commands:

```bash
codelens sessions list
codelens sessions resume SESSION --offline
codelens files SESSION --limit 20 --offset 0
codelens search SESSION "repository"
codelens source SESSION README.md --start 1 --end 20 --offline
codelens refresh SESSION
```

Each open starts an independent session. Refresh returns the same session for an identical snapshot or a new linked session for a changed snapshot. Stored paths, search hits and inclusive line numbers continue to work after the original directory disappears. Use `--json` for structured results and exact source text, including CRLF. Use `--offline` or `CODELENS_OFFLINE=1` to deny remote capture. Stored reads always use local SQLite. Set `CODELENS_HOME` before the first command to place data/config/cache under a chosen directory. Doctor displays the active locations and search engine.

Local capture reads dirty tracked and eligible untracked files. Git worktrees respect repository ignore rules. Plain directories use built-in exclusions. Hidden entries (including .env and .github), dependency/build folders, nested repositories, symlinks, common key files and database files are skipped. GitHub capture indexes the published source archive at the resolved commit. Binary, non-UTF-8 and files over 512 KiB have coverage records; their bodies are unavailable. Capture limits are 3,000 candidate files, 100,000 visited entries and 100 MiB of input (both compressed and expanded limits on archives). A capture records the bytes observed while walking the source. For a precise committed remote revision, supply a SHA. Filename exclusions cannot identify every secret embedded in source text.

Search uses SQLite FTS5/BM25, or a bounded substring scan if the store was created without FTS5. Source reads use the saved bytes in either case. The deployment instructions further below apply to the hosted demo.

## Standalone analysis and chat

Install the current checkout with `python -m pip install .` in your virtual environment. Run `codelens setup` in a terminal to select a provider and enter a model ID. For scripts, use one of these commands with your chosen model:

```bash
codelens setup --provider openai --model "$OPENAI_MODEL"
# Or use a model already installed in your running Ollama instance:
codelens setup --provider ollama --model "$OLLAMA_MODEL"
```

| Provider | Requirements | Streaming and usage |
|---|---|---|
| OpenAI | Set OPENAI_API_KEY in the process environment. Choose an accessible Chat Completions model that supports streaming and max_completion_tokens. | Uses HTTPS and server-sent events. Saves the usage object when returned. |
| Ollama | Start the runtime and install the selected model yourself. Default endpoint is http://127.0.0.1:11434. Use --endpoint for another loopback port. | Reads /api/chat NDJSON, requests num_predict and saves returned prompt/evaluation counts. |

Configuration is user-scoped. The settings file contains the provider, model, endpoint and budgets. Only OpenAI generation reads the credential. Cloud generation sends selected source passages and recent conversation context to the provider, which may retain data under its own policies. Local persistence keeps the saved copy on your machine. Strict offline mode blocks inference for both providers.

```bash
sid=$(codelens open . --json | python -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')
codelens analyze "$sid" --section overview
codelens show "$sid" overview --offline
codelens ask "$sid" "Where does a repository snapshot get saved?"
codelens history "$sid" --offline
```

Use `analyze --section` with **overview, architecture, folders, api, database, diagram, readme, suggestions**. `codelens analyze "$sid" --all` explicitly requests all eight in order. Each completed section commits before the next starts. A retry checks snapshot, passages, prompt, provider/model and options, then reuses completed matches. An explicit `--regenerate` makes another version on the same evidence. Refresh captures changed source in a new session. `sessions resume` lists linked version IDs and statuses. Use `show SESSION SECTION --version ID` to read a particular attempt.

Answers stream as they arrive. Ctrl+C saves the partial response with a cancelled status. If the process exits unexpectedly, reopening its session marks the last checkpoint interrupted. Repeating a section restarts that section. A chat retry with an explicit `--request-id` replays the same completed answer for that session and question. Start a new attempt after a failed question. One generation at a time can run in each session; saved reads remain available during streaming.

Each request uses bounded source samples, with exact file/line references appended to valid evidence labels. The input limit applies to the UTF-8 serialization of the selected messages. Configure `--input-bytes` and `--output-tokens` to fit your chosen model. A terminal provider event and validated citation identifiers (or an explicit insufficient-evidence result) are required for completion. Factual accuracy and Mermaid syntax still require review.

```bash
codelens export "$sid" --format markdown --offline --output analysis.md
codelens export "$sid" --format json --offline --output session.json
codelens export "$sid" --format mermaid --offline --output diagram.mmd
```

Markdown and JSON exports include saved versions, chat and the source excerpts used. Mermaid export writes the selected completed diagram as raw source. Omit `--output` to write to stdout. The first use of an existing schema-v1 database creates a verified `codelens.v1.bak` alongside it before migrating to schema v2.

## Features

- **AI-Powered Analysis** — AI analyzes your entire codebase and generates comprehensive documentation
- **Smart Dashboard** — Architecture, API docs, database schemas, and more in one place
- **Folder Intelligence** — Every folder explained with purpose, responsibilities, and relationships
- **Mermaid Diagrams** — Auto-generated architecture and sequence diagrams
- **Staff Engineer Chat** — Ask any question and get answers like a senior engineer who built the project
- **RAG-Powered Q&A** — Retrieval Augmented Generation for accurate, context-aware answers

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, TailwindCSS, Framer Motion |
| Backend | FastAPI, Python 3.12, SQLAlchemy |
| Database | PostgreSQL + pgvector |
| AI | OpenAI Responses API (gpt-4o-mini, text-embedding-3-small) or Ollama (local LLMs) |
| Orchestration | Docker Compose, Nginx |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API Key (or Ollama for local inference)

### With OpenAI (recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/codelens.git
   cd codelens
   ```

2. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

3. Set a local admin password in `.env`:
   ```
   ADMIN_PASSWORD=choose-a-local-admin-password
   ```

   `OPENAI_API_KEY` and `ENCRYPTION_KEY` may be left empty for local development.
   CodeLens generates a Fernet encryption key and persists it in a Docker volume.

4. Start with Docker Compose:
   ```bash
   docker compose up -d
   ```

5. Open http://localhost:80 in your browser.

6. Open http://localhost/admin/login, enter the admin password, then configure
   the shared OpenAI API key and chat model. The key is encrypted before it is
   stored in PostgreSQL and is never returned to the browser. Public users do
   not have access to this configuration form.

### With Ollama (local, free)

Ollama runs a local LLM on your machine — no API key needed, no API costs.

1. Ensure you have enough RAM (8GB+ recommended). The default models (`llama3.1:8b` + `nomic-embed-text`) require ~6GB.

2. Configure `.env` for Ollama:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_CHAT_MODEL=llama3.1:8b
   OLLAMA_EMBEDDING_MODEL=nomic-embed-text
   # No OPENAI_API_KEY needed
   ```

3. Start with Docker Compose:
   ```bash
   docker compose up -d
   ```

   The Ollama container will automatically pull the configured models on first start (may take a few minutes).

4. Open http://localhost:80 in your browser.

### Switch Between Providers

Change the `LLM_PROVIDER` value in `.env`:

| Provider | `LLM_PROVIDER` | Key Requirement |
|----------|---------------|-----------------|
| OpenAI | `openai` | `OPENAI_API_KEY` required |
| Ollama | `ollama` | No key needed |

After changing, restart the backend:
```bash
docker compose restart backend
```

### Remove Ollama Locally (if using OpenAI only)

If you're using OpenAI and want to free up disk space:

```bash
# Stop all containers and remove Ollama data
docker compose down
docker rmi ollama/ollama:latest
docker volume rm codelens_ollama_data

# Restart without Ollama
docker compose up -d
```

The Ollama service configuration remains in `docker-compose.yml` for future use — it simply won't run unless you set `LLM_PROVIDER=ollama`.

### Development

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Architecture

```
                    ┌─────────────┐
                    │   Browser   │
                    └──────┬──────┘
                           │ HTTP
                    ┌──────▼──────┐
                    │    Nginx    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │
                    │   Backend   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼────┐ ┌─────▼─────┐
        │PostgreSQL│ │ OpenAI  │ │  Frontend  │
        │ + pgvec  │ │  API    │ │ Next.js 15 │
        └──────────┘ └─────────┘ └───────────┘
                           │ (or Ollama)
                    ┌──────▼──────┐
                    │   Ollama    │
                    │ (optional)  │
                    └─────────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/repositories/analyze` | Submit repository for analysis |
| POST | `/api/repositories/{id}/reanalyze` | Regenerate an existing analysis |
| GET | `/api/repositories/{id}` | Get repository status |
| GET | `/api/repositories/{id}/analysis` | Get full analysis data |
| GET | `/api/repositories/{id}/overview` | Get project overview |
| GET | `/api/repositories/{id}/architecture` | Get architecture explanation |
| GET | `/api/repositories/{id}/folders` | Get folder explorer |
| GET | `/api/repositories/{id}/api` | Get API documentation |
| GET | `/api/repositories/{id}/database` | Get database analysis |
| GET | `/api/repositories/{id}/diagram` | Get Mermaid diagram |
| GET | `/api/repositories/{id}/readme` | Get generated README |
| GET | `/api/repositories/{id}/suggestions` | Get improvement suggestions |
| GET | `/api/repositories/{id}/files` | List repository files |
| POST | `/api/repositories/{id}/chat` | Ask a question about the codebase |
| GET | `/api/repositories/{id}/chat-history` | Get chat history |
| GET | `/api/settings/ai` | Get non-secret AI service status |
| GET/POST | `/admin/login` | Owner-only admin login |
| GET/POST | `/admin/settings` | Owner-only OpenAI configuration |

## Project Structure

```
codelens/
├── backend/
│   ├── app/
│   │   ├── api/           # API routes
│   │   ├── core/          # Config, database
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   ├── prompts/       # AI prompts
│   │   └── utils/         # Utilities
│   ├── database/          # Alembic migrations
│   ├── tests/             # Pytest tests
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js pages
│   │   ├── components/    # React components
│   │   ├── services/      # API client
│   │   ├── types/         # TypeScript types
│   │   └── lib/           # Utilities
│   └── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── README.md
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | — | Optional server-side fallback; never expose it to the frontend |
| `LLM_PROVIDER` | No | `openai` | `openai` or `ollama` |
| `OPENAI_CHAT_MODEL` | No | `gpt-4o-mini` | OpenAI chat model |
| `OPENAI_EMBEDDING_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `OLLAMA_CHAT_MODEL` | No | `llama3.1:8b` | Ollama chat model |
| `OLLAMA_EMBEDDING_MODEL` | No | `nomic-embed-text` | Ollama embedding model |
| `DATABASE_URL` | No | PostgreSQL connection string |
| `GITHUB_TOKEN` | No | — | GitHub token (avoids rate limits) |
| `APP_ENVIRONMENT` | Production only | `development` | Set to `production` on Render |
| `ADMIN_PASSWORD` | Local only | — | Plain local-development password |
| `ADMIN_PASSWORD_HASH` | Production | — | Bcrypt hash for the owner password |
| `ADMIN_SESSION_SECRET` | Production | — | Stable 32+ character session-signing secret |
| `ENCRYPTION_KEY` | Production | Auto-generated locally | Stable Fernet key used to encrypt stored API keys |
| `MASTER_KEY_PATH` | No | `./data/master.key` | Persistent master-key location outside Docker |
| `MAX_CONCURRENT_ANALYSES` | No | `2` | Per-backend-instance analysis concurrency cap |
| `ANALYSIS_REQUESTS_PER_HOUR` | No | `5` | Per-IP analysis limit |
| `CHAT_REQUESTS_PER_MINUTE` | No | `30` | Per-IP chat limit |
| `AI_MAX_OUTPUT_TOKENS` | No | `4096` | Maximum model output per generation call |
| `AI_FEATURES_ENABLED` | No | `true` | Owner-controlled emergency kill switch |

When using Docker Compose, the generated master key is stored in the
`backend_secrets` volume. Back up this volume together with PostgreSQL. Losing
the master key makes API keys stored in the database impossible to decrypt.
Production starts in fail-closed mode when required admin or encryption secrets
are missing, or when the stored API key cannot be decrypted.

## Testing

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

## Security

- Repository code is never executed — read-only access
- Maximum repository size: 100 MB
- Maximum files indexed: 3000
- Private repositories are rejected
- Binary files are automatically ignored
- OpenAI configuration writes require a signed owner session
- Admin forms use CSRF protection and login attempts are rate limited
- Public analysis and chat requests have configurable per-IP limits
