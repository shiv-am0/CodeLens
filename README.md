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

3. Add your OpenAI API key to `.env`:
   ```
   OPENAI_API_KEY=sk-your-openai-api-key
   ```

4. Start with Docker Compose:
   ```bash
   docker compose up -d
   ```

5. Open http://localhost:80 in your browser.

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
| `OPENAI_API_KEY` | For OpenAI | — | OpenAI API key |
| `LLM_PROVIDER` | No | `openai` | `openai` or `ollama` |
| `OPENAI_CHAT_MODEL` | No | `gpt-4o-mini` | OpenAI chat model |
| `OPENAI_EMBEDDING_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `OLLAMA_CHAT_MODEL` | No | `llama3.1:8b` | Ollama chat model |
| `OLLAMA_EMBEDDING_MODEL` | No | `nomic-embed-text` | Ollama embedding model |
| `DATABASE_URL` | No | PostgreSQL connection string |
| `GITHUB_TOKEN` | No | — | GitHub token (avoids rate limits) |

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
