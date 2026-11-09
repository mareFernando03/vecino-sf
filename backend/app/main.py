"""API de Vecino SF. Un solo backend sirve a las tres aplicaciones (vecino, autoridad y
recolector): cambian los permisos, no los datos.

    uvicorn app.main:app --reload            (desarrollo, con SQLite)
"""
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from . import eventos
from .db import Base, SessionLocal, preparar_base
from .routers import cuenta, residuos, servicios

conexiones_sse = Gauge("vecino_conexiones_sse", "Clientes conectados al flujo de tiempo real")
conexiones_sse.set_function(eventos.clientes_conectados)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    preparar_base()
    await eventos.iniciar()
    if os.getenv("SIMULADOR_INTERNO") == "1":      # desarrollo: todo en un proceso
        from .simulador import main as simular
        threading.Thread(target=simular, kwargs={"preparar": False}, daemon=True).start()
    yield


app = FastAPI(title="Vecino SF", version="1.0", lifespan=ciclo_de_vida)
for r in (cuenta.router, servicios.router, residuos.router):
    app.include_router(r, prefix="/api")

os.makedirs(servicios.ADJUNTOS, exist_ok=True)
@app.middleware("http")
async def sin_adivinar_tipo(request, call_next):
    """Los adjuntos los sube un usuario: el navegador no debe interpretarlos como otra cosa."""
    r = await call_next(request)
    if request.url.path.startswith("/api/adjuntos/"):
        r.headers["X-Content-Type-Options"] = "nosniff"
    return r


app.mount("/api/adjuntos", StaticFiles(directory=servicios.ADJUNTOS), name="adjuntos")

# /metrics para Prometheus: pedidos por ruta, latencia y errores.
# Los cortes por defecto del histograma terminan en 1 s: con ellos un p95 de 1,5 s se ve como 1 s.
Instrumentator(excluded_handlers=["/metrics", "/salud", "/api/eventos"]).instrument(
    app, latency_lowr_buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)).expose(app)


@app.get("/salud")
async def salud():
    """Sonda de Docker y Kubernetes: ¿el proceso responde? Es async y no toca la base, así no
    hace cola detrás de los pedidos. Si dependiera de la base, con el grupo de conexiones lleno
    la sonda vencería y Kubernetes reiniciaría réplicas sanas justo en el pico de carga."""
    return {"ok": True}


@app.get("/api/salud-replica")          # chequeo completo, accesible desde afuera por nginx
def salud_replica():
    """Qué réplica atendió y si llega a la base. Para diagnóstico, no para las sondas."""
    with SessionLocal() as db:
        db.execute(Base.metadata.tables["usuarios"].select().limit(1))
    return {"ok": True, "replica": os.getenv("HOSTNAME", "local")}
