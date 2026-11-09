"""Prueba de tiempo real entre réplicas (Redis pub/sub) y de privacidad del canal de eventos.

Corre DENTRO de la red de docker compose, con 3 réplicas de la API:

    docker compose up -d --scale api=3
    docker run --rm --network vecino-sf_default -v "$PWD:/w:ro" vecino-carga python /w/prueba_tiempo_real.py

1. Ana abre una conexión /api/eventos directamente contra CADA réplica (api-1, api-2, api-3).
2. La autoridad activa y desactiva una alarma en cada réplica: 6 eventos, cada uno en una réplica.
   Si Redis reparte bien, las tres conexiones de Ana reciben los 6.
3. La autoridad le cambia el estado a un reclamo de Juan: el aviso personal le llega a Juan
   y no a ninguna conexión de Ana.
"""
import asyncio
import json
import socket

import httpx

REPLICAS = ["vecino-sf-api-1", "vecino-sf-api-2", "vecino-sf-api-3"]


def url(replica):
    return f"http://{replica}:8000"


async def login(c, usuario, clave):
    r = await c.post("/api/auth/login", json={"usuario": usuario, "clave": clave})
    return r.json()["token"]


async def escuchar(replica, token, recibidos, listo):
    async with httpx.AsyncClient(base_url=url(replica), timeout=None) as c:
        async with c.stream("GET", "/api/eventos", params={"token": token}) as r:
            listo.set()
            async for linea in r.aiter_lines():
                if linea.startswith("data: "):
                    recibidos.append(json.loads(linea[6:]))


async def main():
    async with httpx.AsyncClient(base_url=url(REPLICAS[0]), timeout=10) as c:
        ana = await login(c, "30111222", "vecino123")
        juan = await login(c, "31222333", "vecino123")
        autoridad = await login(c, "autoridad", "autoridad123")
        h_aut = {"Authorization": f"Bearer {autoridad}"}
        alarma = (await c.get("/api/alarmas")).json()[0]
        reclamo = (await c.post("/api/reclamos", headers={"Authorization": f"Bearer {juan}"},
                                data={"categoria": "Otro", "descripcion": "Prueba de tiempo real",
                                      "direccion": "x"})).json()

    de_ana = {r: [] for r in REPLICAS}
    de_juan: list = []
    listos = [asyncio.Event() for _ in range(len(REPLICAS) + 1)]
    tareas = [asyncio.create_task(escuchar(r, ana, de_ana[r], listos[i])) for i, r in enumerate(REPLICAS)]
    tareas.append(asyncio.create_task(escuchar(REPLICAS[2], juan, de_juan, listos[-1])))
    for e in listos:
        await e.wait()
    await asyncio.sleep(1)

    for replica in REPLICAS:                       # cada cambio entra por una réplica distinta
        async with httpx.AsyncClient(base_url=url(replica), timeout=10) as c:
            for activa in (True, False):
                await c.patch(f"/api/alarmas/{alarma['id']}", headers=h_aut, json={"activa": activa})
    async with httpx.AsyncClient(base_url=url(REPLICAS[1]), timeout=10) as c:
        await c.patch(f"/api/reclamos/{reclamo['id']}", headers=h_aut,
                      json={"estado": "en_curso", "nota": "Prueba de tiempo real"})
    await asyncio.sleep(2)
    for t in tareas:
        t.cancel()

    print("réplicas:", {r: socket.gethostbyname(r) for r in REPLICAS})
    for r in REPLICAS:
        alarmas = [e for e in de_ana[r] if e["tipo"] == "alarma"]
        ajenos = [e for e in de_ana[r] if e["tipo"] == "notificacion" and e["datos"].get("usuario_id")]
        print(f"Ana conectada a {r}: {len(alarmas)} de 6 cambios de alarma · avisos personales ajenos: {len(ajenos)}")
    propio = [e for e in de_juan if e["tipo"] == "notificacion" and str(reclamo["id"]) in e["datos"]["titulo"]]
    print(f"Juan (conectado a {REPLICAS[2]}, el cambio entró por {REPLICAS[1]}): aviso de su reclamo recibido = {len(propio) == 1}")


asyncio.run(main())
