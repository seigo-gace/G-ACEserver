FROM python:3.12-slim-bookworm@sha256:72c1d56207fb14ca388f9b3855ac0e55ab557703928180ec40aa9d4c4f5d5f80
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GSERVER_BIND=0.0.0.0 GSERVER_LOG_DIR=/var/lib/gserver/logs
WORKDIR /opt/gserver
COPY app/ ./app/
RUN mkdir -p /var/lib/gserver/logs && chown -R 65534:65534 /var/lib/gserver
USER 65534:65534
CMD ["python3", "-B", "-u", "app/gserver.py"]
