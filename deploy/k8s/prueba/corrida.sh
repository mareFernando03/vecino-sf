#!/usr/bin/env bash
# Una corrida de la prueba de autoescalado en el clúster k3s de prueba (contenedor vecino-k3s).
#   bash deploy/k8s/prueba/corrida.sh <min> <max> <archivo.log>
# min = max fija las réplicas (línea base); 3 20 es el HPA tal como está en 20-api.yaml.
# Cada 15 s registra el HPA y las conexiones abiertas en PostgreSQL; al final, el resultado de
# los 3 generadores (120 usuarios, 3 minutos).
set -e
MIN=$1; MAX=$2; LOG=$3
export MSYS_NO_PATHCONV=1
K="docker exec -i vecino-k3s kubectl -n vecino-sf"
$K patch hpa api -p "{\"spec\":{\"minReplicas\":$MIN,\"maxReplicas\":$MAX}}" >/dev/null
$K delete job carga --ignore-not-found >/dev/null
$K apply -f /k8s/prueba/carga-job.yaml >/dev/null
{
  echo "# $(date '+%d/%m/%Y %H:%M') · HPA min=$MIN max=$MAX · imagen vecino-sf/api:1.2 (un proceso por pod, pool 4+2)"
  echo "# hora · HPA (cpu actual/objetivo, min, max, réplicas) · conexiones a PostgreSQL"
  inicio=$SECONDS
  while true; do
    estado=$($K get job carga -o jsonpath='{.status.succeeded}/{.status.failed}')
    h=$($K get hpa api --no-headers | awk '{print $3, $4, $5, $6, $7}')
    c=$($K exec postgres-0 -- psql -U vecino -tAc "select count(*) from pg_stat_activity where datname='vecino'")
    echo "$(date +%H:%M:%S)  $h  conexiones_bd=$c"
    [ "$estado" = "3/" ] && break
    case "$estado" in */?*) echo "# el job falló: $estado"; break;; esac
    [ $((SECONDS - inicio)) -gt 330 ] && { echo "# el job no terminó en 330 s: $estado"; break; }
    sleep 15
  done
  echo
  for p in $($K get pods -l job-name=carga -o name); do $K logs "$p" | grep -E "pedidos atendidos|latencia|errores"; done
  echo "# errores de base en los logs de la API (too many clients / QueuePool):"
  for p in $($K get pods -l app=api -o name); do $K logs "$p" 2>&1 | grep -ciE "too many clients|QueuePool" || true; done | awk '{s+=$1} END {print s}'
} | tee "$LOG"
