#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TAG_SUFFIX="${1:-local}"
IMAGE="ls-build-week:${TAG_SUFFIX}"

docker build --pull --file Dockerfile.build-week --tag "$IMAGE" .
docker run --rm "$IMAGE"
