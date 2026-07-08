#!/usr/bin/env bash
set -euo pipefail # Melhora a robustez (encerra em erros ou variáveis nulas)

MODE=${1:-"help"} # Valor padrão caso nenhum argumento seja passado

# Garante que as variáveis de ambiente do Python apontem para a venv
export VIRTUAL_ENV="/opt/venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

terminate() {
    echo "Termination signal received. Shutting down..."
    # Mata os processos filhos (Celery worker/beat)
    pkill -TERM -P $$
    wait
    exit 0
}

trap terminate SIGTERM SIGINT

echo "Waiting for database..."
# Aqui ele já usará o python da venv devido ao PATH
python manage.py wait_for_database

case "$MODE" in
  migrate)
    echo "Running migrations..."
    python manage.py migrate
    ;;

  gunicorn)
    echo "Starting Gunicorn server..."
    # O exec substitui o shell pelo processo do gunicorn (melhor para Docker)
    exec gunicorn atena.wsgi:application \
      --bind 0.0.0.0:"${DJANGO_BACKEND_PORT:-8000}" \
      --workers 10 \
      --max-requests 1000 \
      --limit-request-line 0 \
      --limit-request-field_size 0 \
      --capture-output \
      --enable-stdio-inheritance \
      --timeout 300 \
      --log-level "${DJANGO_LOG_LEVEL:-WARNING}"
    ;;

  celery)
    echo "Starting Celery workers and beat..."
    
    # 1. Worker para a fila padrão (muda para o pool padrão se quiser, ou mantém isolado)
    # Exclui a fila 'etl' usando '-X etl'
    python -m celery -A atena worker -E -l "${DJANGO_LOG_LEVEL:-WARNING}" -X etl &
    DEFAULT_WORKER_PID=$!

    # 2. Worker EXCLUSIVO para a fila 'etl' usando POOL=THREADS
    # Escuta apenas a fila 'etl' usando '-Q etl'
    python -m celery -A atena worker -E -l "${DJANGO_LOG_LEVEL:-WARNING}" -Q etl --pool=threads --concurrency=2 &
    ETL_WORKER_PID=$!

    # 3. Celery Beat
    python -m celery -A atena beat --loglevel "${DJANGO_LOG_LEVEL:-WARNING}" &
    BEAT_PID=$!

    # Aguarda todos os processos
    wait $DEFAULT_WORKER_PID $ETL_WORKER_PID $BEAT_PID
    ;;
    
  *)
    echo "Unknown mode: $MODE"
    echo "Available modes: migrate | gunicorn | celery"
    exit 1
    ;;
esac