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

# Download and compile Spanish translations
RUN mkdir -p /app/superset/translations/es/LC_MESSAGES && \
    curl -fsSL "https://raw.githubusercontent.com/apache/superset/master/superset/translations/es/LC_MESSAGES/messages.po" \
      -o /app/superset/translations/es/LC_MESSAGES/messages.po && \
    pybabel compile -d /app/superset/translations

CMD ["./startup.sh"]
