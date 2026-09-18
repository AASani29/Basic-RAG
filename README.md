# Basic RAG

A full-stack app combining JWT auth, an owner-scoped CRUD resource, and a
retrieval-augmented generation (RAG) chat pipeline: upload a `.txt`/`.pdf`,
ask a question about it, get an answer grounded in the actual document with
its sources cited.

Built as a timed technical assignment, from a plan agreed upfront and built
in verified phases — every non-trivial line has a comment explaining *why*,
not what, and every claim in this README was checked against the running
system, not written from memory.

**Two sibling repos hold the reusable parts of this stack**, with everything
RAG-specific stripped out — start from these for a *different* assignment,
not this one:

- [FastAPI-Template](https://github.com/AASani29/FastAPI-Template) — the
  backend's auth + CRUD pattern, no pgvector/RAG
- [React-Frontend-Template](https://github.com/AASani29/React-Frontend-Template)
  — the frontend's auth + CRUD pattern, no chat page

## Stack

**Backend** — Python 3.11, FastAPI 0.141, SQLAlchemy 2.0 (async, `asyncpg`),
Alembic, PostgreSQL + `pgvector`, JWT auth (`python-jose` + `passlib`/`bcrypt`),
`fastembed` for local embeddings, Groq for chat completions,
`langchain-text-splitters` for chunking, `pypdf` for PDF text.

**Frontend** — React 19, Vite 8, TypeScript, React Router, TanStack Query,
React Context (auth only), axios, Tailwind CSS v4, react-hook-form + zod.

One deliberate, load-bearing deviation from the plan this started from —
covered in full under [Why Groq + local embeddings, not OpenAI](#why-groq--local-embeddings-not-openai-for-everything),
since it's the single most important decision in this repo to be able to
explain.

## Setup

### Prerequisites

Docker Desktop, or (for local dev without it) Python 3.11+ and Node 22+.
A free [Groq API key](https://console.groq.com/keys).

### Full stack, via Docker

```bash
cd backend
cp .env.example .env
# generate a real secret and paste it into .env's JWT_SECRET:
python -c "import secrets; print(secrets.token_urlsafe(32))"
# paste a real key into .env's GROQ_API_KEY

cd ..
docker compose up --build
```

This builds and starts Postgres (with `pgvector` already compiled in) and
the API, running the Alembic migration automatically on every container
start. The API is at `http://localhost:8000` (`/docs` for the interactive
schema); the first RAG request in a fresh container is instant, not slow —
the embedding model is downloaded and cached at *build* time, not on first
use.

Then, in a second terminal, the frontend:

```bash
cd frontend
cp .env.example .env   # VITE_API_URL already points at :8000 by default
npm install
npm run dev
```

Open `http://localhost:5173`.

### Local dev loop (faster edit-test cycle)

Run just the database in Docker, everything else natively:

```bash
docker compose up -d db
cd backend
python -m venv .venv && .venv\Scripts\activate   # source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
alembic upgrade head
python -m scripts.seed          # creates demo@example.com / demopassword123 + 3 items
uvicorn app.main:app --reload
```

```bash
pytest       # 5 tests, needs TEST_DATABASE_URL's database to exist (docker-compose's db creates it on first boot)
ruff check .
```

**Windows note:** the very first embedding call may print a scary-looking
`ERROR ... Permission denied` from `huggingface_hub`'s symlink cache
handling (Developer Mode isn't enabled). It self-recovers by falling back
to a non-symlink cache and the request still succeeds — harmless, not a
broken setup.

### Everything runs off one backend `.env`

No secret is hardcoded anywhere. `backend/.env` (gitignored, never
committed) is the single source of truth — `docker-compose.yml`'s `api`
service reads it via `env_file`, `Settings` reads it directly. The only
override compose applies on top is `DATABASE_URL`, and only because
`localhost` means something different from inside a container than from
your host — see [Trade-offs](#trade-offs--gaps-worth-naming).

## Architecture

```
┌─────────────┐      ┌──────────────────────────────────────────┐      ┌──────────────┐
│   Browser    │      │              FastAPI app                   │      │  PostgreSQL   │
│              │      │                                              │      │  + pgvector   │
│ React 19 SPA │─────▶│ main.py: middleware, exception handlers,     │─────▶│               │
│  (Vite dev   │ HTTP │           router registration                │ SQL  │ users, items, │
│   server or  │◀─────│                                              │◀─────│ document_     │
│  built       │ JSON │ api/routes/*.py  → services/*.py  → db/*.py  │      │  chunks       │
│  assets)     │      │  (auth, items,     (plain functions,  (models,│      │               │
│              │      │   rag)              no HTTP concerns)  engine)│      └──────────────┘
└─────────────┘      └───────────────────┬──────────────────────────┘
                                          │
                              ┌───────────┴───────────┐
                              ▼                        ▼
                     fastembed (local,          Groq (network,
                     ONNX, no network,          chat completions
                     no API key)                 only)
```

Every route depends on `DbSession` and/or `CurrentUser`
(`api/deps.py`) — one dependency pair the whole backend is built around.
Every backend config value lives in `core/config.py`; nothing reads
`os.environ` directly and nothing is hardcoded at a call site. Every error
response — 401, 404, 422, 500, anything — has the identical shape:
`{"error": {"code", "message", "details"}}`, via three global exception
handlers in `main.py`.

On the frontend: `api/client.ts` is the one axios instance for the whole
app (JWT attached by a request interceptor, 401 → hard redirect to
`/login` by a response interceptor); `AuthContext` is the only global
client state; TanStack Query owns all server state; `ProtectedLayout`
combines the route guard and the nav chrome in one component.

## Request flow: asking a question

The path with the most moving parts, traced end to end:

1. **Upload.** `ChatPage` picks a file → `uploadDocument()` sends a
   `multipart/form-data` POST (axios sets the boundary itself — no
   explicit `Content-Type` header) to `POST /rag/documents`.
2. The route validates the extension and size, then `rag_service.py`:
   `extract_text()` (plain decode for `.txt`, `pypdf` page-by-page for
   `.pdf`) → `chunk_text()` (`RecursiveCharacterTextSplitter`,
   `chunk_size=1000`/`chunk_overlap=150`) → `embed_texts()` (local
   `fastembed`, run via `asyncio.to_thread` since ONNX inference is
   synchronous CPU work that would otherwise block the event loop) →
   `store_chunks()` (bulk insert, each row's `embedding` a real
   `vector(384)` column).
3. **Ask.** `ChatPage`'s question box → `chat()` → `POST /rag/chat`.
   `answer_question()` runs two short-circuits, **both before any network
   call**, not just before the paid/chat one:
   - a cheap `COUNT` first — a user with zero uploaded chunks skips even
     the embedding step, since there's nothing to compare the question
     against yet;
   - then, if chunks exist, a real embedding of the question followed by
     a `pgvector` cosine-distance search (`retrieve()`), owner-scoped and
     filtered to `max_cosine_distance <= 0.4`. If nothing survives that
     filter, it stops here too.
4. Only if step 3 found relevant chunks does it call Groq's chat
   completions endpoint, with a system prompt instructing it to answer
   **only** from the provided context and say so if the context doesn't
   contain the answer.
5. The response — `{answer, sources}` — renders in `ChatPage`, sources
   collapsed under a `<details>` per turn.

## Key decisions

### Why Groq + local embeddings, not OpenAI for everything

The original plan locked OpenAI for both halves of RAG. Mid-build, the key
changed to a Groq key, and **Groq has no embeddings endpoint at all**
(confirmed against their own API reference, not assumed) — so this became a
real architecture fork, not a config swap:

- **Chat** → Groq, via the `openai` Python SDK pointed at Groq's
  OpenAI-compatible `base_url`. Model is `openai/gpt-oss-20b` — not the
  `llama-3.3-70b-versatile` Groq's own docs page listed as current, which
  actually 404'd (`model_not_found`) on a real call; corrected against a
  live `GET /models` on the account. Deliberately not `groq/compound`
  (Groq's agentic model that can autonomously browse/tool-call) — that
  would fight the "answer only from provided context" grounding this app's
  correctness depends on.
- **Embeddings** → `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions),
  running locally via ONNX Runtime. Chosen over `sentence-transformers`
  specifically to avoid pulling in the full PyTorch stack for the same job.
  This means embedding a chunk costs **nothing** — no API call, no key, no
  per-request latency to a third party.
- **The retrieval threshold moved from 0.6 to 0.4** as a direct
  consequence. `0.6` was reasoned for OpenAI's larger embedding model's
  distance distribution; measured against `bge-small` directly, a
  genuinely relevant question scored `0.19`, but an *unrelated* one
  ("capital of Mongolia" against a satellite-project document) scored
  `0.56` — under the old cutoff, meaning it would have reached the chat
  model instead of correctly short-circuiting. `0.4` sits cleanly above the
  relevant case and below every irrelevant one actually measured.

### Where the JWT lives on the frontend

`localStorage`, not an `httpOnly` cookie. Trade-off: any XSS on the page
can read a token in `localStorage`; a cookie JS can't touch at all. Chosen
anyway because the cookie route needs CSRF protection and cross-origin
cookie config between the Vite dev server (`:5173`) and the API (`:8000`)
— real work that buys nothing for a short-lived, 60-minute token in a demo.
**For anything handling real user data, prefer an `httpOnly` refresh
cookie + an in-memory access token instead.**

### Chunk size, overlap, top-k

All three live in `core/config.py`, nowhere else:

- **`chunk_size=1000`** characters (~250 tokens): large enough to hold one
  complete idea, small enough that a chunk's single embedding isn't
  diluted across several unrelated topics.
- **`chunk_overlap=150`** (15%): a sentence straddling a chunk boundary is
  still retrievable from whichever side it lands on.
- **`top_k=4`**: sends ~1000 tokens of context to the chat model — several
  chances to contain the answer without burying the model in near-misses
  it has to argue past.

### Why pgvector, not a separate vector database

The data is already in Postgres. A separate vector store means a second
system to run, a second connection to secure, and no transactional
guarantee tying a chunk row to its vector. At this scale, ANN search isn't
even the bottleneck — worth revisiting only past roughly 10M vectors, or
once filtered-ANN latency itself becomes the constraint.

### What happens when nothing relevant is retrieved

Covered in detail under [Request flow](#request-flow-asking-a-question)
above — the short version: two independent short-circuits, both **before**
any network call happens, not just before the paid one. A user with no
documents never even triggers an embedding. A user whose documents exist
but don't match the question never triggers a chat completion. Both return
the same fixed message — `"I don't have anything in your documents about
that."` — with empty sources, deterministically. This is also what makes
the required "chat with no documents" test free of any live dependency.

## Trade-offs & gaps worth naming

**Bugs caught and fixed during the build, not left to be discovered:**

- `passlib` 1.7.4 (last released 2020) is fully broken against `bcrypt`
  5.x — its backend probe hashes a >72-byte test password, which bcrypt
  5.x raises on instead of truncating. Pinned to `bcrypt==4.0.1`, the last
  version that works. The real fix is migrating off `passlib`.
- The test suite's Postgres engine originally lived at module scope;
  `asyncpg` connections are bound to the event loop they were opened on,
  and `pytest-asyncio` gives each test its own loop, so the second test
  onward failed with `another operation is in progress`. Fixed by building
  a fresh engine inside a function-scoped fixture — caught by actually
  running the suite twice, not assumed to work from reading the code.
- The Docker image pre-warms the embedding model at build time so the
  container works offline immediately; doing that as `root` and switching
  to a non-root user *afterward* left a `fastembed`-internal cache
  (separate from and not controlled by `HF_HOME`) owned by a user the
  running app couldn't write to — a permission warning on every single
  embedding call. Fixed by running the pre-warm *after* switching users.

**Deliberately left out**, with the reason:

| Left out | Why |
|---|---|
| Refresh tokens, `httpOnly` cookies | A 60-minute token demonstrates the flow; the cookie route is real added complexity for no demo-time benefit — see JWT decision above |
| RBAC / roles | Owner-scoping (every row filtered by `owner_id`) is what the app actually needed |
| Repository pattern, base service classes, DI framework | Every service has exactly one implementation; an interface layer over one implementation abstracts nothing |
| A separate `documents` table | Nothing today needs document-level metadata beyond the filename already denormalized onto each chunk — add it when delete-by-document or re-indexing is a real requirement |
| Streaming chat (SSE) | Doubles frontend complexity for a demo-only gain |
| Background job queue for ingestion | Upload is synchronous; fine for small files, real cost is the request's own timeout ceiling on a large PDF |
| Reranking, hybrid BM25+vector search | Better as an interview talking point than as code at this scale |
| Rate limiting, request-ID correlation, structured tracing | Production hardening, not a starting point's job |
| Frontend tests, CI, pre-commit | Time-boxed out; see below for what closes this gap first |
| A component library | Tailwind utility classes throughout, per the locked stack |
| Error boundary, optimistic mutations | The frontend has no top-level crash guard, and mutations invalidate-and-refetch rather than update the cache immediately |

## What I'd add with more time

Roughly in the order I'd actually do them:

1. **A `documents` table** — parent row per upload, enabling delete-by-document and re-indexing without touching the chunk schema.
2. **Frontend tests** (Vitest + React Testing Library) and a **CI workflow** running `ruff check`, `pytest`, `tsc -b`, and `npm run lint` on every push — the single highest-leverage gap, since none of this is currently enforced automatically.
3. **Refresh tokens + `httpOnly` cookies**, once this moves past a demo.
4. **Streaming chat responses** (SSE) — the chat call already takes ~1-2s; streaming would make that feel instant.
5. **Reranking** (cross-encoder over the top-`k*2` candidates before truncating to `top_k`) — the cheapest real quality lever left on the table.
6. **A background queue for ingestion** (so a large PDF doesn't hold a request open), plus a documents table's delete/re-index endpoints built on top of it.
7. **An `ErrorBoundary`** around the frontend's `<App />`, and optimistic updates on the items mutations now that the pattern is proven.

## Verifying this works

```bash
# Backend
cd backend && pytest -v          # 5 passed
ruff check . && ruff format --check .

# Frontend
cd frontend && npm run build     # tsc -b && vite build, clean
npm run lint                      # oxlint — one accepted warning, see below

# Full stack
docker compose up --build
curl http://localhost:8000/health   # {"status":"ok","database":"ok"}
```

The one accepted lint warning: `frontend/src/auth/AuthContext.tsx` exports
both `AuthProvider` and `useAuth` from the same file — the standard
Context+hook pattern, which trips oxlint's Fast-Refresh-only-exports-
components rule. Splitting it into two files to silence a stylistic
warning would be exactly the kind of one-implementation abstraction this
project avoided everywhere else; left as-is on purpose.
