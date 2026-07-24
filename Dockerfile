FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PROMPT_ADMIN_HOST=0.0.0.0 \
    PROMPT_ADMIN_PORT=8090

WORKDIR /app

RUN useradd \
    --create-home \
    --uid 10001 \
    --shell /usr/sbin/nologin \
    prompt-admin

COPY requirements.txt ./

RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=prompt-admin:prompt-admin *.py ./
COPY --chown=prompt-admin:prompt-admin api/ ./api/
COPY --chown=prompt-admin:prompt-admin repositories/ ./repositories/
COPY --chown=prompt-admin:prompt-admin schemas/ ./schemas/
COPY --chown=prompt-admin:prompt-admin services/ ./services/
COPY --chown=prompt-admin:prompt-admin ui/ ./ui/
COPY --chown=prompt-admin:prompt-admin database/ ./database/
COPY --chown=prompt-admin:prompt-admin templates/ ./templates/
COPY --chown=prompt-admin:prompt-admin static/ ./static/

USER prompt-admin

EXPOSE 8090

CMD ["sh", "-c", "exec uvicorn app:create_app --factory --host \"$PROMPT_ADMIN_HOST\" --port \"$PROMPT_ADMIN_PORT\""]
