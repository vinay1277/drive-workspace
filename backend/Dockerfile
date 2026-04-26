FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY drive_workspace ./drive_workspace
COPY reference_server ./reference_server

RUN pip install --upgrade pip && pip install -e .[flask,postgres]

EXPOSE 8080

CMD ["flask", "--app", "reference_server.app", "run", "--host=0.0.0.0", "--port=8080"]
