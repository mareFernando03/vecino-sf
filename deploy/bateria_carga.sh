#!/usr/bin/env bash
# Batería completa de la prueba de carga en docker compose; escribe docs/prueba-carga.log.
#   bash deploy/bateria_carga.sh
set -e
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1
LOG=../docs/prueba-carga.log
W="$(pwd -W 2>/dev/null || pwd)"
uno() {  # un generador dentro de la red de Docker
  docker run --rm --network vecino-sf_default -e PYTHONIOENCODING=utf-8 -v "$W:/w:ro" \
    vecino-carga python /w/prueba_carga.py --url http://web "$@"
}
{
  echo "# $(date '+%d/%m/%Y %H:%M') · imagen vecino-sf/api:1.2 (un proceso por contenedor, pool 5+10)"
  echo "# docker compose, 1 generador dentro de la red de Docker (60 usuarios, 25 s)"
  for r in 1 3 6; do
    docker compose up -d --scale api=$r >/dev/null 2>&1; sleep 12
    echo "=== $r réplica(s)"
    uno --usuarios 60 --segundos 25
  done
  echo
  echo "# 3 generadores en paralelo (120 usuarios, 25 s)"
  for r in 1 3 6; do bash carga_paralela.sh $r 3 40; done
  echo
  echo "# Redundancia: 3 réplicas, 60 usuarios, se tira una réplica (docker kill) a los 8 s de empezar."
  docker compose up -d --scale api=3 >/dev/null 2>&1; sleep 12
  (sleep 8; docker kill vecino-sf-api-2 >/dev/null; echo "# docker kill vecino-sf-api-2 a las $(date +%H:%M:%S)" >&2) &
  uno --usuarios 60 --segundos 25
  wait
} > "$LOG" 2>&1
docker compose up -d --scale api=3 >/dev/null 2>&1
