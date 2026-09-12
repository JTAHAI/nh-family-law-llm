#!/usr/bin/env sh
set -eu
IMAGE_TAG="${IMAGE_TAG:-nh-family-law-llm:local}"
DATA_ROOT="${NH_FAMILY_LAW_DATA_ROOT:-../NH_FAMILY_LAW_LLM_data}"
PORT="${PORT:-8000}"
REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
mkdir -p "$DATA_ROOT"
docker run --rm \
  --name nh-family-law-llm-api \
  --user 10001:10001 \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -e NH_FAMILY_LAW_DATA_ROOT=/data \
  -e PYTHONPATH=/app \
  -p "127.0.0.1:${PORT}:8000" \
  -v "${DATA_ROOT}:/data" \
  -v "${REPO_ROOT}:/app:ro" \
  "$IMAGE_TAG"
