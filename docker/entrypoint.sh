#!/bin/bash
set -e

echo "Starting Horilla CRM..."

# Wait for PostgreSQL to be ready (with timeout)
echo "Waiting for PostgreSQL..."
MAX_TRIES=30
COUNT=0
while ! nc -z db 5432; do
  COUNT=$((COUNT + 1))
  if [ "$COUNT" -ge "$MAX_TRIES" ]; then
    echo "ERROR: PostgreSQL not available after $MAX_TRIES attempts"
    exit 1
  fi
  sleep 1
done
echo "PostgreSQL is ready!"

# Run migrations
python manage.py migrate --noinput

# Compile .po translation files into the .mo binaries Django actually loads
# at runtime -- .mo is gitignored, so this must run on every container start
# or newly added/edited translations (e.g. Persian strings) never show up.
python manage.py compilemessages

# Collect static files
python manage.py collectstatic --noinput

echo "Starting server..."
exec "$@"
