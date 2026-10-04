FROM eclipse-temurin:21-jre-jammy AS java
FROM python:3.11-slim-bookworm
COPY --from=java /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk \
    PATH=/opt/java/openjdk/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HQ_DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home hq \
    && mkdir /app/data && chown hq:hq /app/data
COPY --chown=hq:hq hq_service ./hq_service
USER hq
EXPOSE 8080
CMD ["python", "-m", "hq_service"]
