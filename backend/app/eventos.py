"""Tiempo real con Server-Sent Events.

Cada cliente abierto (mapa de bicis, panel de la autoridad, ruta del recolector) mantiene
una conexión /eventos, que exige sesión. Cuando algo cambia, el backend publica un evento:
los cambios de estado del mapa le llegan a todos, y un aviso personal (una notificación con
usuario_id) sólo a la conexión de ese usuario. El filtro lo hace el servidor, no la app.

Con varias réplicas de la API, un cambio que ocurre en la réplica A tiene que llegarle
a un cliente conectado a la réplica B. Para eso se usa Redis pub/sub: cada réplica publica
en el canal y todas escuchan. Sin Redis (desarrollo), el reparto es en memoria.
"""
import asyncio
import json
import logging
import os

CANAL = "vecino-sf:eventos"
REDIS_URL = os.getenv("REDIS_URL")

_clientes: dict[asyncio.Queue, int] = {}      # cola de cada conexión -> id del usuario
_loop: asyncio.AbstractEventLoop | None = None
_redis = None
_escucha: asyncio.Task | None = None
log = logging.getLogger("vecino.eventos")


def clientes_conectados() -> int:
    return len(_clientes)


def _dueno(mensaje: str) -> int | None:
    """Id del único usuario que puede ver este evento, o None si es público."""
    m = json.loads(mensaje)
    return m["datos"].get("usuario_id") if m["tipo"] == "notificacion" else None


def _repartir(mensaje: str):
    dueno = _dueno(mensaje)
    for q, usuario_id in list(_clientes.items()):
        if dueno is not None and dueno != usuario_id:
            continue                 # aviso personal de otro usuario: no sale de esta réplica
        if q.qsize() < 100:          # un cliente lento no frena a los demás
            q.put_nowait(mensaje)


def publicar(tipo: str, datos: dict):
    """Se llama desde código síncrono (los endpoints). No bloquea."""
    mensaje = json.dumps({"tipo": tipo, "datos": datos}, default=str)
    if _redis is not None:
        _redis.publish(CANAL, mensaje)
    elif _loop is not None:
        _loop.call_soon_threadsafe(_repartir, mensaje)


def conectar_publicador():
    """Para procesos sin event loop (el simulador): sólo publican, no reparten."""
    global _redis
    if REDIS_URL:
        import redis
        _redis = redis.Redis.from_url(REDIS_URL)


async def iniciar():
    """Arranca con la app. Con Redis, una tarea escucha el canal y reparte localmente."""
    global _loop, _redis, _escucha
    _loop = asyncio.get_running_loop()
    if not REDIS_URL:
        return
    import redis
    import redis.asyncio as aioredis
    _redis = redis.Redis.from_url(REDIS_URL)

    async def escuchar():
        while True:                  # si Redis se cae o corta la conexión, vuelve a suscribirse
            try:
                sub = aioredis.Redis.from_url(REDIS_URL).pubsub()
                await sub.subscribe(CANAL)
                async for m in sub.listen():
                    if m["type"] == "message":
                        _repartir(m["data"].decode())
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("se cortó la escucha de Redis (%s): reintento en 2 s", e)
                await asyncio.sleep(2)

    # Hay que guardar la tarea: asyncio sólo guarda una referencia débil y, sin otra, el
    # recolector de basura puede destruirla. Pasó bajo carga: la réplica dejó de repartir
    # eventos sin ningún error visible ("Task was destroyed but it is pending").
    _escucha = asyncio.create_task(escuchar())


async def flujo(usuario_id: int):
    """Generador para StreamingResponse: un evento SSE por mensaje, y un latido cada 15 s
    para que proxies y balanceadores no corten la conexión por inactividad."""
    q: asyncio.Queue = asyncio.Queue()
    _clientes[q] = usuario_id
    try:
        yield "retry: 3000\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=15)
                yield f"data: {msg}\n\n"
            except asyncio.TimeoutError:
                yield ": latido\n\n"
    finally:
        _clientes.pop(q, None)
