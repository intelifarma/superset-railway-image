FROM apache/superset:latest-dev

USER root

ARG DATABASE_URL
ARG REDISHOST
ARG REDISPORT
ARG REDIS_URL
ARG SUPERSET_SECRET_KEY
ARG SUPERSET_PORT=8088

ENV PYTHONPATH="/app/pythonpath:/app/docker/pythonpath_prod"
ENV REDIS_HOST="${REDISHOST}"
ENV REDIS_PORT=${REDISPORT}
ENV REDIS_URL="${REDIS_URL}"
ENV SUPERSET_CACHE_REDIS_URL=${REDIS_URL}
ENV SUPERSET_ENV="production"
ENV SUPERSET_LOAD_EXAMPLES="no"
ENV SUPERSET_SECRET_KEY="${SUPERSET_SECRET_KEY}"
ENV CYPRESS_CONFIG=False
ENV SUPERSET_PORT="${SUPERSET_PORT}"

ENV SQLALCHEMY_DATABASE_URI="${DATABASE_URL}"
ENV SUPERSET_CONFIG_PATH=/app/docker/superset_config.py

EXPOSE 8088

# Copy files
COPY startup.sh ./startup.sh
COPY bootstrap.sh /app/docker/docker-bootstrap.sh
COPY superset_config.py /app/docker/superset_config.py

RUN chmod +x ./startup.sh
RUN chmod +x /app/docker/docker-bootstrap.sh

# Install Prophet for Superset native forecasting
RUN pip install prophet --no-cache-dir

# Compile ALL translations that ship with the image (includes Spanish)
# Use -f to force compilation even if .po has minor formatting issues
RUN find /app/superset/translations -name "messages.po" -exec sh -c \
    'dir=$(dirname "$1"); pybabel compile -f -i "$1" -o "$dir/messages.mo" 2>/dev/null' _ {} \; ; \
    ls -la /app/superset/translations/es/LC_MESSAGES/ 2>/dev/null || \
    echo "WARNING: Spanish translations not found, downloading..." && \
    mkdir -p /app/superset/translations/es/LC_MESSAGES && \
    (curl -fsSL "https://raw.githubusercontent.com/apache/superset/master/superset/translations/es/LC_MESSAGES/messages.po" \
      -o /tmp/messages_es.po 2>/dev/null || \
     curl -fsSL "https://raw.githubusercontent.com/apache/superset/main/superset/translations/es/LC_MESSAGES/messages.po" \
      -o /tmp/messages_es.po 2>/dev/null) && \
    [ -f /tmp/messages_es.po ] && \
    pybabel compile -f -i /tmp/messages_es.po -o /app/superset/translations/es/LC_MESSAGES/messages.mo 2>/dev/null; \
    echo "Translation .mo files:" && find /app/superset/translations -name "*.mo" -ls

CMD ["./startup.sh"]
