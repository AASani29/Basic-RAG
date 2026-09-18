# Single-stage, not multi-stage: this app has no compiled build step of its
# own to discard afterward (no C extensions built from source, no frontend
# bundle), so the usual multi-stage size win doesn't apply here — it would
# only add complexity without removing anything.
FROM python:3.11-slim

WORKDIR /app

# libgomp1: onnxruntime (fastembed's inference backend) links against OpenMP
# for CPU parallelism. python:3.11-slim doesn't ship it, and its absence
# fails as an import error at first embedding call, not at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Own env var, not the default ~/.cache: keeps the model download under a
# path this Dockerfile controls.
ENV HF_HOME=/app/.hf_cache

# requirements.txt copied alone, before the rest of the app: Docker caches
# each layer by its inputs, so `docker build` after an app-code-only change
# reuses this pip-install layer instead of re-downloading every package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user, created and switched to BEFORE the pre-warm step below —
# not after. fastembed writes to more than just HF_HOME: it keeps a second,
# separate cache under /tmp (independent of the HF_HOME setting above,
# confirmed by testing the built image, not assumed) for a HuggingFace Hub
# "tree cache" feature. Pre-warming as root first and switching users
# afterward leaves that /tmp cache root-owned, which the app then can't
# write to at runtime — surfacing as a "Permission denied" warning on every
# single embedding call. Running the pre-warm AS appuser means every cache
# directory fastembed touches, wherever it ends up, is owned by the same
# user that runs the app.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Downloads and caches the embedding model at BUILD time, not on the first
# real request. The alternative is a user's first chat message silently
# blocking for several seconds — or failing outright, if the running
# container has no outbound internet — while it fetches ~70MB from
# HuggingFace. Paying that cost once, here, means the container works
# immediately and fully offline after it starts.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# Unbuffered stdout: without this, Python buffers output when it isn't
# attached to a real terminal (which it isn't, inside a container), so `docker
# compose logs` can lag behind or withhold the app's log lines entirely.
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
