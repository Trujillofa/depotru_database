#!/usr/bin/env bash
# Nightly advisor cross-sell affinity refresh -> Neon (writes ONLY with --apply).
# J3 is read-only. Retries up to 3 times: J3 intermittently returns
# j3_unavailable (ConnectionError); a single-shot cron would lose nights.
# Env override for tests: AFF_ATTEMPTS, AFF_RETRY_SLEEP, AFF_INBOX_ENV,
# AFF_REPO_DIR, AFF_PY, AFF_ENV_FILE.
#
# Regla de la firma (hallazgo 7): NO se corre --apply si el env no carga.
# Antes, si `. env` fallaba (archivo ausente o exit 1), el wrapper seguía
# y lanzaba el job con ADVISOR_DATABASE_URL vacía.
set -u
: "${AFF_INBOX_ENV:=/home/yderf/.config/depotru-inbox/env}"
: "${AFF_REPO_DIR:=/home/yderf/Projects/depotru_database-wt/bff-clean-main}"
: "${AFF_PY:=$AFF_REPO_DIR/.venv/bin/python}"
: "${AFF_ENV_FILE:=/home/yderf/Projects/depotru-inbox-prod/.env.local}"
# Credenciales J3 (DB_HOST/DB_USER/...). El worktree no tiene .env propio y
# Database() no las encuentra: sin esto el job fallaba cada noche con
# j3_unavailable: ConnectionError (5-18 nov 2026). Es el mismo archivo que
# carga depotru-bff-clean.service.
: "${AFF_J3_ENV:=/home/yderf/Projects/depotru_database/.env}"

cd "$AFF_REPO_DIR" || exit 1

if [ ! -f "$AFF_J3_ENV" ]; then
  echo "$(date -Is) env J3 $AFF_J3_ENV no existe - ABORT sin --apply"
  exit 1
fi
set -a
# shellcheck disable=SC1090
. "$AFF_J3_ENV"
rc=$?
set +a
if [ "$rc" -ne 0 ] || [ -z "${DB_HOST:-}" ]; then
  echo "$(date -Is) carga del env J3 falló (rc=${rc}) - ABORT sin --apply"
  exit 1
fi

if [ ! -f "$AFF_INBOX_ENV" ]; then
  echo "$(date -Is) env $AFF_INBOX_ENV no existe - ABORT sin --apply"
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "$AFF_INBOX_ENV"
rc=$?
set +a
if [ "$rc" -ne 0 ]; then
  echo "$(date -Is) carga del env falló (rc=${rc}) - ABORT sin --apply"
  exit 1
fi
if [ -z "${ADVISOR_DATABASE_URL:-}" ] && [ -z "${DATABASE_URL:-}" ]; then
  echo "$(date -Is) sin DATABASE_URL tras la carga - ABORT sin --apply"
  exit 1
fi
export ADVISOR_DATABASE_URL="${ADVISOR_DATABASE_URL:-$DATABASE_URL}"
attempts="${AFF_ATTEMPTS:-3}"
sleep_s="${AFF_RETRY_SLEEP:-600}"
i=1
while [ "$i" -le "$attempts" ]; do
  if PYTHONPATH=src "$AFF_PY" -m business_analyzer.jobs.cross_sell_affinity \
      --env-file "$AFF_ENV_FILE" --apply --json; then
    echo "$(date -Is) ok (intento ${i}/${attempts})"
    exit 0
  fi
  echo "$(date -Is) intento ${i}/${attempts} fallo"
  i=$((i + 1))
  [ "$i" -le "$attempts" ] && sleep "$sleep_s"
done
echo "$(date -Is) FALLO tras ${attempts} intentos - requiere revision"
exit 1
