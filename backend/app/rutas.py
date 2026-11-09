"""Rutas de recolección optimizadas.

1. Orden: vecino más cercano desde la base, mejorado con 2-opt (invierte tramos mientras
   eso acorte el total). Para 20-40 paradas da resultados a pocos % del óptimo en
   milisegundos, y es fácil de explicar y de probar.
2. Trazado: se le pide el recorrido por calles a OSRM (motor de ruteo de código abierto
   sobre OpenStreetMap). Si no responde, se dibujan tramos rectos y la ruta igual sirve.
"""
import math
import os

import httpx

# Base operativa de recolección (dato simulado, centro-oeste de la ciudad).
BASE = (-31.4330, -62.1010)
OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")


def distancia_km(a, b):
    """Haversine: distancia en línea recta sobre la esfera terrestre."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def largo(recorrido):
    return sum(distancia_km(recorrido[i], recorrido[i + 1]) for i in range(len(recorrido) - 1))


def vecino_mas_cercano(puntos, inicio=BASE):
    pendientes = list(range(len(puntos)))
    orden, actual = [], inicio
    while pendientes:
        j = min(pendientes, key=lambda k: distancia_km(actual, puntos[k]))
        orden.append(j)
        pendientes.remove(j)
        actual = puntos[j]
    return orden


def dos_opt(orden, puntos, inicio=BASE):
    """Ruta cerrada: sale de la base y vuelve a la base."""
    def total(o):
        return largo([inicio] + [puntos[k] for k in o] + [inicio])
    mejor, mejoro = orden[:], True
    while mejoro:
        mejoro = False
        for i in range(len(mejor) - 1):
            for j in range(i + 1, len(mejor)):
                nuevo = mejor[:i] + mejor[i:j + 1][::-1] + mejor[j + 1:]
                if total(nuevo) < total(mejor) - 1e-9:
                    mejor, mejoro = nuevo, True
    return mejor


def optimizar(puntos, inicio=BASE):
    """Devuelve (orden, km) para una lista de (lat, lng)."""
    if not puntos:
        return [], 0.0
    orden = dos_opt(vecino_mas_cercano(puntos, inicio), puntos, inicio)
    km = largo([inicio] + [puntos[k] for k in orden] + [inicio])
    return orden, round(km, 2)


def trazado(recorrido):
    """Geometría por calles de OSRM; si falla, tramos rectos."""
    coords = ";".join(f"{lng},{lat}" for lat, lng in recorrido)
    try:
        r = httpx.get(f"{OSRM_URL}/route/v1/driving/{coords}",
                      params={"overview": "full", "geometries": "geojson"}, timeout=4)
        r.raise_for_status()
        ruta = r.json()["routes"][0]
        return [[lat, lng] for lng, lat in ruta["geometry"]["coordinates"]], round(ruta["distance"] / 1000, 2), "osrm"
    except Exception:
        return [list(p) for p in recorrido], round(largo(recorrido), 2), "recto"
