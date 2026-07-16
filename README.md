# CodeLens

**Understand Any Codebase in Minutes**

CodeLens is a production-ready AI-powered developer tool that analyzes public GitHub repositories and generates comprehensive documentation, architecture diagrams, API summaries, and intelligent Q&A using Retrieval Augmented Generation (RAG).

## Features

- **AI-Powered Analysis** — GPT-5.5 analyzes your entire codebase and generates comprehensive documentation
- **Smart Dashboard** — Architecture, API docs, database schemas, and more in one place
- **Folder Intelligence** — Every folder explained with purpose, responsibilities, and relationships
- **Mermaid Diagrams** — Auto-generated architecture and sequence diagrams
- **Staff Engineer Chat** — Ask any question and get answers like a senior engineer who built the project
- **RAG-Powered Q&A** — Retrieval Augmented Generation for accurate, context-aware answers

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, TailwindCSS, Framer Motion |
| Backend | FastAPI, Python 3.12, SQLAlchemy, Alembic |
| Database | PostgreSQL + pgvector |
| AI | OpenAI Responses API, GPT-5.5, text-embedding-3-small |
| Background | Celery + Redis |
| Auth | JWT (python-jose) |
| Deployment | Docker, Docker Compose, Nginx |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API Key

### Setup

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
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼───┐ ┌─────▼──────┐
       │   FastAPI   │ │Redis │ │  Frontend  │
       │   Backend   │ │      │ │ Next.js 15 │
       └──────┬──────┘ └──────┘ └────────────┘
              │
    ┌─────────┼─────────┐
    │         │         │
┌───▼───┐ ┌──▼──┐ ┌────▼────┐
│Postgre│ │Celery│ │  OpenAI │
│ + vec │ │Worker│ │   API   │
└───────┘ └─────┘ └─────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| POST | `/api/repositories/analyze` | Submit repository for analysis |
| GET | `/api/repositories/{id}` | Get repository status |
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
│   │   ├── core/          # Config, database, security
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   ├── prompts/       # AI prompts
│   │   ├── workers/       # Celery tasks
│   │   └── utils/         # Utilities
│   ├── database/          # Alembic migrations
│   ├── tests/             # Pytest tests
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js pages
│   │   ├── components/    # React components
│   │   ├── hooks/         # React hooks
│   │   ├── services/      # API client
│   │   ├── types/         # TypeScript types
│   │   └── lib/           # Utilities
│   └── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── README.md
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `DATABASE_URL` | No | PostgreSQL connection string |
| `REDIS_URL` | No | Redis connection string |
| `JWT_SECRET` | No | JWT signing secret |
| `GITHUB_TOKEN` | No | GitHub token (avoids rate limits) |

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
- JWT authentication for API access
