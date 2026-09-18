"""POST /rag/documents (upload), POST /rag/chat."""

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.rag import ChatRequest, ChatResponse, SourceChunk, UploadResponse
from app.services import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])
settings = get_settings()

# Matches what extract_text() in rag_service.py actually knows how to parse.
# Enforced here rather than inside the service so the accepted-types list has
# exactly one place to look, and so a rejected file never reaches the service.
_ALLOWED_EXTENSIONS = (".txt", ".pdf")


@router.post("/documents", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile, db: DbSession, current_user: CurrentUser
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(_ALLOWED_EXTENSIONS):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Only .txt and .pdf files are supported"
        )

    content = await file.read()
    # Checked AFTER reading, not before: Content-Length can be absent or
    # spoofed, so the only reliable size is the number of bytes actually
    # received. This bounds worst-case memory, not worst-case network
    # transfer — an honest limitation for a synchronous upload endpoint,
    # not a hardened one. See README trade-offs.
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_bytes // 1024}KB limit",
        )

    text = rag_service.extract_text(file.filename, content)
    chunks = rag_service.chunk_text(text)
    if not chunks:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No extractable text found in file")

    embeddings = await rag_service.embed_texts(chunks)
    chunk_count = await rag_service.store_chunks(
        db, current_user.id, file.filename, chunks, embeddings
    )
    return UploadResponse(filename=file.filename, chunk_count=chunk_count)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: DbSession, current_user: CurrentUser) -> ChatResponse:
    answer, chunks = await rag_service.answer_question(db, current_user.id, payload.question)
    sources = [
        SourceChunk(filename=c.filename, chunk_index=c.chunk_index, content=c.content)
        for c in chunks
    ]
    return ChatResponse(answer=answer, sources=sources)
