# syntax=docker/dockerfile:1
FROM rust:slim-bookworm AS build
WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY qmoosa-core qmoosa-core
COPY qmoosa-wasm qmoosa-wasm
COPY src src
RUN cargo build --release --locked --package qmoosa-app

FROM python:3.13-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 QMOOSA_CORE_BIN=/opt/qmoosa/bin/qmoosa-app QMOOSA_BIND=0.0.0.0 PORT=8080
WORKDIR /opt/qmoosa
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt && useradd --uid 10001 --create-home qmoosa
COPY --from=build /build/target/release/qmoosa-app /opt/qmoosa/bin/qmoosa-app
COPY app.py service.py project.json ./
COPY web web
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=3)"
CMD ["python", "service.py"]
