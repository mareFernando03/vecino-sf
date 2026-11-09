"""Prueba de carga: muchos vecinos usando la app a la vez.

    python deploy/prueba_carga.py --url http://localhost:8080 --usuarios 60 --segundos 30

Cada usuario virtual repite un recorrido típico (mapa de bicis, cuenta tributaria, mis
reclamos, notificaciones, puntos de reciclaje) sin pausas. Informa pedidos por segundo,
latencias, errores y cuántos pedidos atendió cada réplica.
"""
import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx

RECORRIDO = ["/api/bicis/estaciones?lat=-31.42&lng=-62.08", "/api/tributaria/cedulones", "/api/reclamos",
             "/api/notificaciones", "/api/residuos/puntos-reciclaje", "/api/alarmas"]


async def usuario(cliente, token, hasta, tiempos, errores):
    h = {"Authorization": f"Bearer {token}"}
    while time.perf_counter() < hasta:
        for ruta in RECORRIDO:
            t0 = time.perf_counter()
            try:
                r = await cliente.get(ruta, headers=h)
                if r.status_code >= 500:
                    errores[r.status_code] += 1
                else:
                    tiempos.append(time.perf_counter() - t0)
            except httpx.HTTPError as e:
                errores[type(e).__name__] += 1


async def main(a):
    limites = httpx.Limits(max_connections=a.usuarios, max_keepalive_connections=a.usuarios)
    async with httpx.AsyncClient(base_url=a.url, timeout=20, limits=limites) as c:
        token = (await c.post("/api/auth/login", json={"usuario": "30111222", "clave": "vecino123"})).json()["token"]
        replicas = Counter()
        for _ in range(60):                       # cómo reparte el balanceador
            replicas[(await c.get("/api/salud-replica")).json().get("replica")] += 1
        tiempos, errores = [], Counter()
        inicio = time.perf_counter()
        await asyncio.gather(*(usuario(c, token, inicio + a.segundos, tiempos, errores) for _ in range(a.usuarios)))
        dur = time.perf_counter() - inicio
    tiempos.sort()
    p = lambda q: tiempos[min(len(tiempos) - 1, int(q * len(tiempos)))] * 1000
    print(f"usuarios simultáneos : {a.usuarios}")
    print(f"pedidos atendidos    : {len(tiempos)} en {dur:.1f} s  = {len(tiempos) / dur:.0f} pedidos/s")
    print(f"latencia             : mediana {statistics.median(tiempos) * 1000:.0f} ms · p95 {p(0.95):.0f} ms · p99 {p(0.99):.0f} ms")
    print(f"errores              : {sum(errores.values())} {dict(errores) if errores else ''}")
    print(f"reparto entre réplicas (60 pedidos): {dict(replicas)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--usuarios", type=int, default=60)
    ap.add_argument("--segundos", type=int, default=30)
    asyncio.run(main(ap.parse_args()))
