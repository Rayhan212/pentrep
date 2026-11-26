# pentrep container image (FR-61): docker run --rm -v "$PWD:/work" ghcr.io/rayhan212/pentrep build findings.yaml

# --- Build stage: the wheel plus runtime requirements pinned by uv.lock (with hashes) -------------
FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv build --wheel --out-dir /dist \
    && uv export --frozen --no-dev --no-emit-project --format requirements-txt -o /dist/requirements.txt

# --- Runtime stage --------------------------------------------------------------------------------
FROM python:3.12-slim
# Pango/HarfBuzz are the system libraries WeasyPrint needs for PDF output.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 fontconfig \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /dist /tmp/dist
RUN pip install --no-cache-dir --require-hashes -r /tmp/dist/requirements.txt \
    && pip install --no-cache-dir --no-deps /tmp/dist/*.whl \
    && rm -rf /tmp/dist
RUN useradd --create-home --uid 1000 pentrep \
    && mkdir /work && chown pentrep:pentrep /work
USER pentrep
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["pentrep"]
CMD ["--help"]
