# Pinned release: latest-dev ships a development build with root access and dev tooling.
FROM apache/superset:6.1.0

USER root

# Runtime settings (DATABASE_URL, REDIS_URL, SUPERSET_SECRET_KEY, ...) come from the
# platform environment and are not baked into image layers.
ENV SUPERSET_ENV="production" \
    SUPERSET_LOAD_EXAMPLES="no" \
    CYPRESS_CONFIG="False" \
    SUPERSET_CONFIG_PATH=/app/docker/superset_config.py

EXPOSE 8088

COPY startup.sh ./startup.sh
COPY bootstrap.sh /app/docker/docker-bootstrap.sh
COPY superset_config.py /app/docker/superset_config.py

# Windows checkouts (core.autocrlf) store shell scripts with CRLF, which breaks the shebang.
RUN sed -i 's/\r$//' ./startup.sh /app/docker/docker-bootstrap.sh && \
    chmod +x ./startup.sh /app/docker/docker-bootstrap.sh

# The lean image has no metadata-database driver; this deployment stores metadata in PostgreSQL.
# Prophet provides native forecasting. Both are installed into the image venv, as the upstream docs show.
RUN . /app/.venv/bin/activate && \
    uv pip install --no-cache psycopg2-binary prophet

# The lean image ships only the Spanish .po catalog. pybabel exits non-zero because
# upstream's catalog has 14 entries with placeholder mismatches; it skips those entries
# and still writes the .mo (same tolerance as upstream's Dockerfile). The build therefore
# verifies the output itself and fails if the catalog cannot be loaded.
RUN . /app/.venv/bin/activate && \
    (pybabel compile -f \
      -i /app/superset/translations/es/LC_MESSAGES/messages.po \
      -o /app/superset/translations/es/LC_MESSAGES/messages.mo || true) && \
    python -c "import gettext; gettext.GNUTranslations(open('/app/superset/translations/es/LC_MESSAGES/messages.mo','rb'))"

# Spinner asset the backend reads from the frontend tree (superset/views/base.py at 6.1.0).
RUN mkdir -p /app/superset-frontend/packages/superset-ui-core/src/components/assets/images && \
    curl -fsSL "https://raw.githubusercontent.com/apache/superset/6.1.0/superset-frontend/packages/superset-ui-core/src/components/assets/images/loading.svg" \
      -o /app/superset-frontend/packages/superset-ui-core/src/components/assets/images/loading.svg

USER superset

CMD ["./startup.sh"]
