#!/usr/bin/env bash
set -euo pipefail
LOCAL_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')
UTC_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
printf '{"local":"%s","utc":"%s"}\n' "$LOCAL_TIME" "$UTC_TIME"
