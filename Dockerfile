FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd \
    --create-home \
    --uid 10001 \
    --shell /usr/sbin/nologin \
    prompt-admin

COPY requirements.txt ./

RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=prompt-admin:prompt-admin *.py ./
COPY --chown=prompt-admin:prompt-admin database/ ./database/
COPY --chown=prompt-admin:prompt-admin templates/ ./templates/
COPY --chown=prompt-admin:prompt-admin static/ ./static/

USER prompt-admin

EXPOSE 8090

CMD ["python", "app.py"]