"""RAG pipeline: extract -> chunk -> embed -> store, and embed -> retrieve ->
answer. Plain functions, same shape as auth_service.py and item_service.py —
no class, no base pipeline abstraction, because there is exactly one pipeline.
"""

import asyncio
import io
from functools import lru_cache

from fastapi import HTTPException, status
from fastembed import TextEmbedding
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import DocumentChunk

settings = get_settings()

# Shown verbatim when retrieval finds nothing relevant (or the user has no
# documents at all) — see answer_question. Deliberately not phrased as an
# apology or hedge: it states the actual limitation (documents only) so a
# user isn't left wondering whether the app is broken.
_NO_CONTEXT_ANSWER = "I don't have anything in your documents about that."

_SYSTEM_PROMPT = (
    "You answer questions using ONLY the context provided below. "
    "If the context does not contain the answer, say you don't know. "
    "Never use outside knowledge, and never guess."
)


@lru_cache
def _get_chat_client() -> AsyncOpenAI:
    """Constructed lazily, on first actual use — NOT at module import time.

    This module is imported by main.py at startup regardless of whether
    GROQ_API_KEY is set (main.py imports every route module to register it).
    AsyncOpenAI raises immediately if api_key is empty, so building the
    client eagerly at import time would crash the whole app — health and auth
    included — whenever no key is configured. Building it lazily means a
    missing key only breaks the RAG chat route, which is the behavior
    config.py's own comment already promises.

    Points at Groq, not OpenAI: Groq's chat completions API is a drop-in
    match for OpenAI's request/response shape, so the same `openai` SDK
    client works unmodified against it — only api_key and base_url change.
    """
    return AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)


@lru_cache
def _get_embedding_model() -> TextEmbedding:
    """Also lazy, for a different reason than the chat client: constructing
    this loads an ONNX inference session and, on the very first run ever,
    downloads the ~70MB model file. That cost is real (seconds, not
    milliseconds) — paying it at import time would slow down every app
    startup, including `uvicorn` boots and test runs that never touch RAG.
    Building it on first actual use means only the first RAG request pays it,
    once per process.
    """
    return TextEmbedding(model_name=settings.embedding_model)


def extract_text(filename: str, content: bytes) -> str:
    """.txt is decoded directly; .pdf is parsed page by page.

    Caller (the route) is responsible for rejecting any other extension
    before this is reached — this function only knows how to handle the two
    types the upload endpoint advertises.
    """
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        # extract_text() returns None for a page with no extractable text
        # (e.g. a scanned image page with no OCR layer) rather than raising.
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8", errors="replace")


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    # Strip + drop blanks: a scanned-PDF page with no text layer contributes
    # an empty or whitespace-only fragment, which would otherwise become a
    # zero-content row with its own (meaningless) embedding.
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    # fastembed's embed() runs ONNX inference synchronously on the CPU — a
    # blocking call. Calling it directly here would freeze the whole async
    # event loop (every other in-flight request) for however long inference
    # takes. to_thread() moves it to a worker thread instead — the same
    # reasoning that ruled out a sync DB driver in db/session.py. embed()
    # also returns a lazy generator, not a list, so the list() has to happen
    # inside the thread too, or the generator would still run its (blocking)
    # inference lazily back on the event loop when iterated afterwards.
    model = _get_embedding_model()
    vectors = await asyncio.to_thread(lambda: list(model.embed(texts)))
    return [vector.tolist() for vector in vectors]


async def store_chunks(
    db: AsyncSession,
    owner_id: int,
    filename: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> int:
    # strict=True: if a future change makes embed_texts return a different
    # count than it was given (a partial batch failure, say), this raises
    # immediately instead of silently pairing the wrong chunk with the wrong
    # vector.
    rows = [
        DocumentChunk(
            owner_id=owner_id, filename=filename, chunk_index=i, content=chunk, embedding=embedding
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
    ]
    db.add_all(rows)
    await db.commit()
    return len(rows)


async def retrieve(
    db: AsyncSession, owner_id: int, question_embedding: list[float]
) -> list[DocumentChunk]:
    # Cosine distance: 0 = identical direction, 2 = opposite. Filtering AND
    # ordering by the same expression means Postgres can use the HNSW index
    # (built with vector_cosine_ops in migration 0001) for both at once.
    distance = DocumentChunk.embedding.cosine_distance(question_embedding)
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.owner_id == owner_id)
        .where(distance <= settings.max_cosine_distance)
        .order_by(distance)
        .limit(settings.top_k)
    )
    rows = await db.scalars(stmt)
    return list(rows)


async def answer_question(
    db: AsyncSession, owner_id: int, question: str
) -> tuple[str, list[DocumentChunk]]:
    """Returns (answer, source_chunks). Two short-circuits, both before the
    expensive/paid calls:

    1. No documents at all for this user -> skip even the embedding step.
       There is nothing to compare the question against yet, so embedding it
       is pure wasted CPU (embeddings run locally, so there's no API cost to
       save — but a cold model load + ONNX inference is not free either).
       This is also what makes "chat with no documents" (one of the required
       tests) deterministic and independent of any network call.
    2. Documents exist, but none score within MAX_COSINE_DISTANCE of this
       specific question -> skip the chat completion call (the one step that
       does cost a real network round-trip, to Groq). Answering from an
       empty/irrelevant context is exactly how a RAG app invents a confident-
       sounding wrong answer; refusing is the correct behavior here, not a
       fallback.
    """
    has_any_document = await db.scalar(
        select(DocumentChunk.id).where(DocumentChunk.owner_id == owner_id).limit(1)
    )
    if has_any_document is None:
        return _NO_CONTEXT_ANSWER, []

    [question_embedding] = await embed_texts([question])
    chunks = await retrieve(db, owner_id, question_embedding)
    if not chunks:
        return _NO_CONTEXT_ANSWER, []

    context = "\n\n".join(f"[{c.filename} chunk {c.chunk_index}]\n{c.content}" for c in chunks)
    response = await _get_chat_client().chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    answer = response.choices[0].message.content
    if not answer:
        # A finish_reason other than "stop" (content filter, length cutoff)
        # can leave this empty. Surfacing our own message beats returning an
        # empty 200 the frontend would render as a blank bubble.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="The model returned no answer. Try again."
        )
    return answer, chunks
