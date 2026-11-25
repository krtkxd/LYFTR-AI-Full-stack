# Stage 1: install dependencies into a prefix
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: small runtime image
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
COPY --from=builder /install /usr/local
WORKDIR /app
COPY app ./app
RUN useradd -m appuser && mkdir -p /data && chown appuser /data
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
