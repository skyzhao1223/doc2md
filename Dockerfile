# doc2md — official image
# Includes optional OCR (RapidOCR/ONNX Runtime). stdio by default;
# set DOC2MD_TRANSPORT=streamable-http for a direct HTTP endpoint.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp1 is required by onnxruntime (OCR)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir ".[ocr]"

# Run as non-root
RUN useradd --create-home --uid 10001 doc2md
USER doc2md

ENV DOC2MD_TRANSPORT=stdio
CMD ["python", "-m", "doc2md.server"]
