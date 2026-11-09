#!/usr/bin/env bash
# Corre N generadores de carga a la vez dentro de la red de Docker y suma los resultados.
# Un solo generador (un proceso de Python) se satura antes que 6 réplicas de la API.
#   bash deploy/carga_paralela.sh <réplicas> <generadores> <usuarios_por_generador>
set -e
cd "$(dirname "$0")"
REPLICAS=${1:-3}; GEN=${2:-3}; USU=${3:-40}
export MSYS_NO_PATHCONV=1
docker compose up -d --scale api="$REPLICAS" >/dev/null 2>&1
sleep 12
TMP=.carga; rm -rf "$TMP"; mkdir -p "$TMP"
for i in $(seq 1 "$GEN"); do
  docker run --rm --network vecino-sf_default -e PYTHONIOENCODING=utf-8 -v "$(pwd -W 2>/dev/null || pwd):/w:ro" \
    vecino-carga python /w/prueba_carga.py --url http://web --usuarios "$USU" --segundos 25 > "$TMP/$i.txt" 2>&1 &
done
wait
PYTHONIOENCODING=utf-8 python - "$TMP" "$REPLICAS" "$GEN" "$USU" <<'PY'
import re, sys, pathlib
d, rep, gen, usu = sys.argv[1], *sys.argv[2:]
pps = med = p95 = err = 0
for f in pathlib.Path(d).glob("*.txt"):
    t = f.read_text(encoding="utf-8")
    pps += int(re.search(r"= (\d+) pedidos/s", t).group(1))
    m = re.search(r"mediana (\d+) ms · p95 (\d+) ms", t)
    med, p95 = max(med, int(m.group(1))), max(p95, int(m.group(2)))
    err += int(re.search(r"errores\s+: (\d+)", t).group(1))
print(f"{rep} réplicas · {gen} generadores x {usu} usuarios = {int(gen) * int(usu)} simultáneos: "
      f"{pps} pedidos/s · mediana {med} ms · p95 {p95} ms (peor generador) · {err} errores")
PY
