#!/usr/bin/env sh
# Validate Prometheus config and rules with promtool, and the Grafana files with pytest.
# Run from code/final: sh scripts/check_configs.sh
set -eu

PROM_IMAGE=prom/prometheus:v3.1.0

docker run --rm -v "$PWD/prometheus:/etc/prometheus:ro" --entrypoint promtool "$PROM_IMAGE" \
  check config /etc/prometheus/prometheus.yml

docker run --rm -v "$PWD/prometheus:/etc/prometheus:ro" --entrypoint promtool "$PROM_IMAGE" \
  check rules /etc/prometheus/rules/crawlbase.rules.yml

docker run --rm -v "$PWD/prometheus:/etc/prometheus:ro" --entrypoint promtool "$PROM_IMAGE" \
  test rules /etc/prometheus/tests/crawlbase.rules.test.yml

docker run --rm -v "$PWD:/app" -w /app python:3.11-slim sh -c \
  "pip install -q -r requirements-dev.txt && python -m pytest -q tests/test_configs.py"
