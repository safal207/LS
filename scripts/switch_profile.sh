#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILES_DIR="$ROOT_DIR/config/profiles"
TARGET_FILE="$ROOT_DIR/config/local.yaml"

usage() {
  cat <<USAGE
Usage:
  scripts/switch_profile.sh <profile-name>

Available profiles:
  interview_quality
  balanced_daily
  offline_survival
USAGE
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

PROFILE_NAME="$1"
SOURCE_FILE="$PROFILES_DIR/${PROFILE_NAME}.yaml"

if [[ ! -d "$PROFILES_DIR" ]]; then
  echo "❌ Profiles directory not found: $PROFILES_DIR"
  exit 1
fi

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "❌ Unknown profile: $PROFILE_NAME"
  echo "Available:"
  find "$PROFILES_DIR" -maxdepth 1 -type f -name '*.yaml' -printf '  - %f\n' | sed 's/\.yaml$//'
  exit 1
fi

cp "$SOURCE_FILE" "$TARGET_FILE"

echo "✅ Switched profile to: $PROFILE_NAME"
echo "   Source: $SOURCE_FILE"
echo "   Target: $TARGET_FILE"
