#!/usr/bin/env bash
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
set -e

#
# Always install local overrides first
#
/app/docker/docker-bootstrap.sh

STEP_CNT=4

echo_step() {
cat <<EOF

######################################################################


Init Step ${1}/${STEP_CNT} [${2}] -- ${3}


######################################################################

EOF
}
if [ -z "${SUPERSET_SECRET_KEY:-}" ] || [ "${SUPERSET_SECRET_KEY}" = "CHANGE_ME" ]; then
    echo "SUPERSET_SECRET_KEY must be set to a unique value in the platform environment." >&2
    exit 1
fi
if [ -z "${SUPERSET_ADMIN_PASSWORD:-}" ] || [ -z "${SUPERSET_ADMIN_EMAIL:-}" ]; then
    echo "SUPERSET_ADMIN_EMAIL and SUPERSET_ADMIN_PASSWORD must be set in the platform environment." >&2
    exit 1
fi
ADMIN_PASSWORD="${SUPERSET_ADMIN_PASSWORD}"
# If Cypress run – export env variables for the test configuration
if [ "$CYPRESS_CONFIG" == "true" ]; then
    export SUPERSET_CONFIG=tests.integration_tests.superset_test_config
    export SUPERSET_TESTENV=true
    export SUPERSET__SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://superset:superset@db:5432/superset
fi
# Initialize the database
echo_step "1" "Starting" "Applying DB migrations"
superset db upgrade
echo_step "1" "Complete" "Applying DB migrations"

# Create an admin user
echo_step "2" "Starting" "Setting up admin user (admin)"
superset fab create-admin \
              --username admin \
              --firstname Superset \
              --lastname Admin \
              --email "${SUPERSET_ADMIN_EMAIL}" \
              --password $ADMIN_PASSWORD
echo_step "2" "Complete" "Setting up admin user"
# Create default roles and permissions
echo_step "3" "Starting" "Setting up roles and perms"
superset init
echo_step "3" "Complete" "Setting up roles and perms"

if [ "$SUPERSET_LOAD_EXAMPLES" = "yes" ]; then
    # Load some data to play with
    echo_step "4" "Starting" "Loading examples"
    # If Cypress run which consumes superset_test_config – load required data for tests
    if [ "$CYPRESS_CONFIG" == "true" ]; then
        superset load_test_users
        superset load_examples --load-test-data
    else
        superset load_examples --force
    fi
    echo_step "4" "Complete" "Loading examples"
fi

echo "Starting web app..."
/app/docker/entrypoints/run-server.sh