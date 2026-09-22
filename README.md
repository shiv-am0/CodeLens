# CodeLens

**Understand Any Codebase in Minutes**

CodeLens is a production-ready AI-powered developer tool that analyzes public GitHub repositories and generates comprehensive documentation, architecture diagrams, API summaries, and intelligent Q&A using Retrieval Augmented Generation (RAG).

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
