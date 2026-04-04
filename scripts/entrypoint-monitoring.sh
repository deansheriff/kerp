#!/bin/sh
# Install monitoring dependencies if not already present
python -c "import logging_loki" 2>/dev/null || pip install -q python-logging-loki==0.3.1 rfc3339==6.2 2>/dev/null
python -c "import sentry_sdk" 2>/dev/null || pip install -q "sentry-sdk[fastapi]>=2.0" 2>/dev/null

exec "$@"
