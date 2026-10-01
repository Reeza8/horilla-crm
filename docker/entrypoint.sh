#!/bin/bash
set -e

echo "Starting Horilla CRM..."

# Wait for the database to be ready (with timeout). The host and port come
# from the Django settings (DATABASE_URL, or DB_HOST/DB_PORT), so the database
# does not have to be a Compose service named "db".
echo "Waiting for the database..."
python manage.py wait_for_db --attempts 30

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
