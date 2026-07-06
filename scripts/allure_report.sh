#!/usr/bin/env bash
#
# Generate the Allure report, carrying TREND HISTORY across runs.
#
# Allure's Trend / History / retry-trend / duration-trend / categories-trend
# widgets are built from a history/ folder that `allure generate` READS from the
# results dir and WRITES into the report dir. `--clean` wipes the report (and its
# history) each run, so unless the previous report's history is copied back into
# the results dir BEFORE generating, every report is "build 1 of 1" and the Trend
# shows "nothing to show". This script does that carry, so trends accumulate as
# long as the report dir persists between runs (≥2 builds before a line appears).
#
# Env:
#   ALLURE_DIR     results dir   (default: reports/allure-results)
#   ALLURE_REPORT  report dir    (default: reports/allure-report)
#   SERVE=1        open a live server after generating
#
# Usage:  scripts/allure_report.sh           # generate, history carried
#         SERVE=1 scripts/allure_report.sh    # generate + open live
set -uo pipefail

ALLURE_DIR="${ALLURE_DIR:-reports/allure-results}"
ALLURE_REPORT="${ALLURE_REPORT:-reports/allure-report}"

if ! command -v allure >/dev/null 2>&1; then
  echo "  Allure CLI not found — install with: brew install allure ; then: allure serve ${ALLURE_DIR}"
  exit 0
fi

# Carry the previous report's history into the results dir so trends accumulate.
if [ -d "${ALLURE_REPORT}/history" ]; then
  rm -rf "${ALLURE_DIR}/history"
  cp -R "${ALLURE_REPORT}/history" "${ALLURE_DIR}/history"
fi

if allure generate --clean "${ALLURE_DIR}" -o "${ALLURE_REPORT}" >/dev/null 2>&1; then
  echo "  Report:  ${ALLURE_REPORT}/index.html   (trend history carried)"
else
  echo "  (allure generate failed — raw results in ${ALLURE_DIR})"
fi
echo "  Open it: allure open ${ALLURE_REPORT}"
echo "  Or live: allure serve ${ALLURE_DIR}"
if [ "${SERVE:-0}" = "1" ]; then
  allure serve "${ALLURE_DIR}"
fi
