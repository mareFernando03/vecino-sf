"""Sesión, notificaciones (historial, preferencias, push) y eventos en tiempo real."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import eventos
from ..auth import emitir_token, requiere, usuario_actual, usuario_de_token, verificar
from ..db import SessionLocal, get_db
from ..models import Notificacion, Preferencias, SuscripcionPush, Usuario
from ..notificar import TIPOS, VAPID_PUBLIC, notificar

router = APIRouter()


class Login(BaseModel):
    usuario: str
    clave: str


@router.post("/auth/login")
def login(datos: Login, db: Session = Depends(get_db)):
    u = db.scalar(select(Usuario).where(Usuario.usuario == datos.usuario.strip()))
    if u is None or not verificar(datos.clave, u.clave_hash):
        raise HTTPException(401, "Usuario o clave incorrectos")
    return {"token": emitir_token(u), "usuario": yo(u)}


@router.get("/auth/yo")
def yo(u: Usuario = Depends(usuario_actual)):
    return {"id": u.id, "usuario": u.usuario, "nombre": u.nombre, "rol": u.rol, "barrio": u.barrio}


@router.get("/eventos")
def flujo_eventos(token: str):
    """SSE con sesión. EventSource no puede mandar el encabezado Authorization, así que el
    token viaja como parámetro (por HTTPS); nginx no registra la query de esta ruta.
    Los avisos personales sólo le llegan a su dueño (ver eventos._repartir)."""
    with SessionLocal() as db:       # sesión corta: no queda tomada mientras dure la conexión
        u = usuario_de_token(token, db)
    return StreamingResponse(eventos.flujo(u.id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── 7. Notificaciones al vecino ─────────────────────────────────────────────
@router.get("/notificaciones")
def historial(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    prefs = db.get(Preferencias, u.id)
    q = (select(Notificacion)
         .where(or_(Notificacion.usuario_id == u.id, Notificacion.usuario_id.is_(None)))
         .order_by(Notificacion.fecha.desc()).limit(100))
    from ..notificar import quiere
    return [n.datos() for n in db.scalars(q).all()
            if n.usuario_id == u.id or quiere(prefs, n.tipo, n.barrio)]


class Prefs(BaseModel):
    tipos: list[str]
    barrios: list[str]
    frecuencia: str = "inmediata"


@router.get("/notificaciones/preferencias")
def ver_prefs(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = db.get(Preferencias, u.id)
    return p.datos() if p else {"tipos": TIPOS, "barrios": [], "frecuencia": "inmediata"}


@router.put("/notificaciones/preferencias")
def guardar_prefs(datos: Prefs, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if datos.frecuencia not in ("inmediata", "resumen_diario"):
        raise HTTPException(422, "Frecuencia inválida")
    invalidos = set(datos.tipos) - set(TIPOS)
    if invalidos:
        raise HTTPException(422, f"Tipos inválidos: {sorted(invalidos)}")
    p = db.get(Preferencias, u.id) or Preferencias(usuario_id=u.id)
    p.tipos, p.barrios, p.frecuencia = datos.tipos, datos.barrios, datos.frecuencia
    db.add(p)
    db.commit()
    return p.datos()


@router.get("/push/clave-publica")
def clave_publica():
    return {"clave": VAPID_PUBLIC}


class Suscripcion(BaseModel):
    endpoint: str
    keys: dict


@router.post("/push/suscribir")
def suscribir(s: Suscripcion, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    previa = db.scalar(select(SuscripcionPush).where(SuscripcionPush.endpoint == s.endpoint))
    if previa:
        previa.usuario_id = u.id
    else:
        db.add(SuscripcionPush(usuario_id=u.id, endpoint=s.endpoint,
                               p256dh=s.keys["p256dh"], auth=s.keys["auth"]))
    db.commit()
    return {"ok": True}


class Aviso(BaseModel):
    tipo: str
    titulo: str
    cuerpo: str
    barrio: str | None = None
    enlace: str | None = None


@router.post("/notificaciones/enviar")
def enviar(a: Aviso, _: Usuario = Depends(requiere("autoridad")), db: Session = Depends(get_db)):
    """La municipalidad publica un aviso (corte, obra, evento, campaña de reciclaje...)."""
    if a.tipo not in TIPOS:
        raise HTTPException(422, "Tipo inválido")
    return notificar(db, a.tipo, a.titulo, a.cuerpo, barrio=a.barrio, enlace=a.enlace).datos()
