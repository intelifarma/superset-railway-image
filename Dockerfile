FROM apache/superset:latest

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

RUN pip install psycopg2-binary
RUN pip install google
RUN pip install google-api-core
RUN pip install google.cloud.bigquery
RUN pip install google.cloud.storage
RUN pip install --upgrade google-api-python-client

# Specify the startup script as the entry point
COPY startup.sh ./startup.sh
COPY bootstrap.sh /app/docker/docker-bootstrap.sh
COPY superset_config.py superset_config.py

RUN apt-get update
RUN apt-get install gettext -y
RUN envsubst < "superset_config.py" > "/app/docker/superset_config.py"

RUN chmod +x ./startup.sh
RUN chmod +x /app/docker/docker-bootstrap.sh

RUN export SUPERSET_CONFIG_PATH=/app/docker/superset_config.py
CMD sh -c "./startup.sh"
