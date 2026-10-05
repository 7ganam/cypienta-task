FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=mock_cypienta_api.container_settings \
    HOME=/home/app

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app \
    && mkdir /data && chown app:app /data
COPY --chown=app:app . .
USER app
EXPOSE 40759
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:40759/health', timeout=2)"
CMD ["gunicorn", "--bind", "0.0.0.0:40759", "--workers", "1", "mock_cypienta_api.wsgi:application"]