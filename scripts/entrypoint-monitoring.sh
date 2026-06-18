#!/bin/sh

# Install monitoring dependencies if not already present
python -c "import logging_loki" 2>/dev/null || pip install -q python-logging-loki==0.3.1 rfc3339==6.2 2>/dev/null
python -c "import sentry_sdk" 2>/dev/null || pip install -q "sentry-sdk[fastapi]>=2.0" 2>/dev/null

APP_ROOT="${APP_ROOT:-/app}"

is_web_command() {
  case "$1" in
    gunicorn|uvicorn)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

seed_admin_user() {
  retries="${SEED_ADMIN_RETRIES:-12}"
  delay="${SEED_ADMIN_RETRY_DELAY_SECONDS:-5}"
  attempt=1

  while [ "$attempt" -le "$retries" ]; do
    echo "Seeding admin user (attempt $attempt/$retries)..."
    if python "$APP_ROOT/scripts/seed_admin.py"; then
      echo "Admin seed completed."
      return 0
    fi

    attempt=$((attempt + 1))
    if [ "$attempt" -le "$retries" ]; then
      echo "Admin seed failed; retrying in ${delay}s..."
      sleep "$delay"
    fi
  done

  echo "Admin seed failed after $retries attempts."
  return 1
}

run_migrations() {
  retries="${MIGRATION_RETRIES:-12}"
  delay="${MIGRATION_RETRY_DELAY_SECONDS:-5}"
  attempt=1

  while [ "$attempt" -le "$retries" ]; do
    echo "Running database migrations (attempt $attempt/$retries)..."
    if python -m alembic upgrade heads; then
      echo "Migrations completed."
      return 0
    fi

    attempt=$((attempt + 1))
    if [ "$attempt" -le "$retries" ]; then
      echo "Migrations failed; retrying in ${delay}s..."
      sleep "$delay"
    fi
  done

  echo "Migrations failed after $retries attempts."
  return 1
}

seed_demo_data() {
  retries="${SEED_DEMO_RETRIES:-3}"
  delay="${SEED_DEMO_RETRY_DELAY_SECONDS:-5}"
  attempt=1

  while [ "$attempt" -le "$retries" ]; do
    echo "Seeding demo tech company data (attempt $attempt/$retries)..."
    if python "$APP_ROOT/scripts/seed_demo_tech_company.py"; then
      echo "Demo seed completed."
      return 0
    fi

    attempt=$((attempt + 1))
    if [ "$attempt" -le "$retries" ]; then
      echo "Demo seed failed; retrying in ${delay}s..."
      sleep "$delay"
    fi
  done

  echo "Demo seed failed after $retries attempts."
  return 1
}

if is_web_command "$1"; then
  run_migrations || exit 1

  case "${SEED_ADMIN_ON_START:-true}" in
    false|False|FALSE|0|no|No|NO|off|Off|OFF)
      echo "Admin seed skipped."
      ;;
    *)
      seed_admin_user || exit 1
      ;;
  esac

  case "${SEED_DEMO_ON_START:-true}" in
    false|False|FALSE|0|no|No|NO|off|Off|OFF)
      echo "Demo seed skipped."
      ;;
    *)
      seed_demo_data || exit 1
      ;;
  esac

  # The entrypoint owns startup seeding after migrations, so do not repeat it
  # in the FastAPI lifespan hook.
  export SEED_ADMIN_ON_START=false
fi

exec "$@"
