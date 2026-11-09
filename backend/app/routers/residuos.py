"""Sistema de gestión de residuos (caso Geo Maps): tres roles sobre los mismos datos.

- Vecino: registra sus residuos, pide recolección de especiales, ve puntos y horarios.
- Autoridad: mapa en tiempo real, planifica y asigna rutas, gestiona incidentes y campañas.
- Recolector: ve su ruta, escanea el QR del contenedor para registrar la recolección y
  reporta incidentes.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import eventos
from ..auth import requiere, usuario_actual
from ..db import get_db
from ..models import (Contenedor, Incidente, PuntoReciclaje, Recoleccion, RegistroResiduo, Ruta,
                      Solicitud, Usuario)
from ..notificar import notificar
from ..rutas import BASE, optimizar, trazado
from ..seed import HORARIOS

router = APIRouter(prefix="/residuos")
vecino = requiere("vecino")
autoridad = requiere("autoridad")
recolector = requiere("recolector")

CATEGORIAS = ["organico", "reciclable", "voluminoso", "peligroso", "otros"]


# ─── Aplicación ciudadana ────────────────────────────────────────────────────
class Registro(BaseModel):
    categoria: str
    cantidad: float = Field(gt=0, le=1000)
    unidad: str = Field(pattern="^(kg|bolsas|unidades)$")


@router.post("/registros", status_code=201)
def registrar(r: Registro, u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    if r.categoria not in CATEGORIAS:
        raise HTTPException(422, "Categoría inválida")
    reg = RegistroResiduo(usuario_id=u.id, **r.model_dump())
    db.add(reg)
    db.commit()
    return reg.datos()


@router.get("/registros")
def mis_registros(u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    filas = db.scalars(select(RegistroResiduo).where(RegistroResiduo.usuario_id == u.id)
                       .order_by(RegistroResiduo.fecha.desc())).all()
    desde = datetime.now() - timedelta(days=30)
    resumen = {}
    for f in filas:
        if f.fecha >= desde:
            clave = f"{f.categoria} ({f.unidad})"
            resumen[clave] = round(resumen.get(clave, 0) + f.cantidad, 2)
    return {"registros": [f.datos() for f in filas], "ultimos_30_dias": resumen}


class NuevaSolicitud(BaseModel):
    tipo: str = Field(pattern="^(reciclable|voluminoso|peligroso)$")
    descripcion: str = Field(min_length=5, max_length=500)
    direccion: str = Field(min_length=3)
    lat: float = Field(ge=-31.50, le=-31.36)     # dentro del ejido (aprox.)
    lng: float = Field(ge=-62.16, le=-62.00)


@router.post("/solicitudes", status_code=201)
def solicitar(s: NuevaSolicitud, u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    sol = Solicitud(usuario_id=u.id, **s.model_dump())
    db.add(sol)
    db.commit()
    eventos.publicar("solicitud", {"id": sol.id, "estado": sol.estado})   # sin domicilio: el canal es de todos
    return sol.datos()


@router.get("/solicitudes")
def solicitudes(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    q = select(Solicitud).order_by(Solicitud.creada.desc())
    if u.rol == "vecino":
        q = q.where(Solicitud.usuario_id == u.id)
    return [s.datos() for s in db.scalars(q).all()]


@router.get("/puntos-reciclaje")
def puntos(db: Session = Depends(get_db)):
    return [p.datos() for p in db.scalars(select(PuntoReciclaje)).all()]


@router.get("/horarios")
def horarios():
    return HORARIOS


# ─── Panel de autoridades ────────────────────────────────────────────────────
@router.get("/mapa")
def mapa(_: Usuario = Depends(requiere("autoridad", "recolector")), db: Session = Depends(get_db)):
    """Todo lo que hay que dibujar: contenedores con su llenado, solicitudes pendientes,
    rutas activas e incidentes abiertos."""
    return {
        "base": BASE,
        "contenedores": [c.datos() for c in db.scalars(select(Contenedor)).all()],
        "solicitudes": [s.datos() for s in db.scalars(select(Solicitud).where(
            Solicitud.estado != "recolectada")).all()],
        "rutas": [_ruta(db, r) for r in db.scalars(select(Ruta).where(Ruta.estado != "completada")).all()],
        "incidentes": [i.datos() for i in db.scalars(select(Incidente).where(
            Incidente.estado == "abierto").order_by(Incidente.fecha.desc())).all()],
    }


@router.get("/recolectores")
def recolectores(_: Usuario = Depends(autoridad), db: Session = Depends(get_db)):
    return [{"id": u.id, "nombre": u.nombre} for u in
            db.scalars(select(Usuario).where(Usuario.rol == "recolector")).all()]


class Plan(BaseModel):
    recolector_id: int
    umbral_llenado: int = Field(70, ge=0, le=100)   # contenedores a partir de este %
    barrios: list[str] = []                          # vacío = toda la ciudad
    incluir_solicitudes: bool = True


@router.post("/rutas", status_code=201)
def planificar(p: Plan, _: Usuario = Depends(autoridad), db: Session = Depends(get_db)):
    """Elige las paradas (contenedores llenos y solicitudes pendientes), las ordena con el
    optimizador y se la asigna a un recolector. Lo que ya está en otra ruta activa no se repite."""
    rec = db.get(Usuario, p.recolector_id)
    if rec is None or rec.rol != "recolector":
        raise HTTPException(404, "Recolector inexistente")
    if db.get_bind().dialect.name == "postgresql":
        # Dos planificaciones a la vez leerían las mismas paradas libres: se hacen de a una
        # (el candado dura hasta el commit). Planificar es raro, así que esperar no cuesta nada.
        db.execute(text("SELECT pg_advisory_xact_lock(2027)"))
    ocupados = {(par["tipo"], par["id"]) for r in db.scalars(select(Ruta).where(Ruta.estado != "completada")).all()
                for par in r.paradas if not par["hecha"]}
    q = select(Contenedor).where(Contenedor.llenado >= p.umbral_llenado, Contenedor.estado == "ok")
    if p.barrios:
        q = q.where(Contenedor.barrio.in_(p.barrios))
    paradas = [{"tipo": "contenedor", "id": c.id, "codigo": c.codigo, "lat": c.lat, "lng": c.lng, "hecha": False}
               for c in db.scalars(q).all() if ("contenedor", c.id) not in ocupados]
    if p.incluir_solicitudes:
        paradas += [{"tipo": "solicitud", "id": s.id, "codigo": f"SOL-{s.id}", "lat": s.lat, "lng": s.lng,
                     "hecha": False, "detalle": f"{s.tipo}: {s.descripcion}"}
                    for s in db.scalars(select(Solicitud).where(Solicitud.estado == "pendiente")).all()]
    if not paradas:
        raise HTTPException(409, "No hay paradas que cumplan el criterio")
    orden, km_recto = optimizar([(x["lat"], x["lng"]) for x in paradas])
    paradas = [paradas[k] for k in orden]
    geometria, km, fuente = trazado([BASE] + [(x["lat"], x["lng"]) for x in paradas] + [BASE])
    r = Ruta(recolector_id=rec.id, paradas=paradas, distancia_km=km, geometria=geometria)
    db.add(r)
    db.flush()
    for x in paradas:
        if x["tipo"] == "solicitud":
            s = db.get(Solicitud, x["id"])
            s.estado, s.ruta_id = "asignada", r.id
    db.commit()
    notificar(db, "residuos", "Nueva ruta asignada", f"{len(paradas)} paradas, {km} km.",
              usuario_id=rec.id, enlace="/recolector")
    eventos.publicar("ruta", _ruta(db, r))
    return _ruta(db, r) | {"km_linea_recta": km_recto, "trazado": fuente}


def _ruta(db, r: Ruta):
    d = r.datos()
    d["recolector"] = db.get(Usuario, r.recolector_id).nombre
    d["hechas"] = sum(1 for x in r.paradas if x["hecha"])
    return d


@router.get("/rutas")
def rutas(_: Usuario = Depends(autoridad), db: Session = Depends(get_db)):
    return [_ruta(db, r) for r in db.scalars(select(Ruta).order_by(Ruta.creada.desc()).limit(50)).all()]


@router.patch("/incidentes/{iid}")
def resolver(iid: int, _: Usuario = Depends(autoridad), db: Session = Depends(get_db)):
    i = db.get(Incidente, iid)
    if i is None:
        raise HTTPException(404, "Incidente inexistente")
    i.estado = "resuelto"
    if i.contenedor_id:
        c = db.get(Contenedor, i.contenedor_id)
        c.estado = "ok"
        eventos.publicar("contenedor", c.datos())
    db.commit()
    eventos.publicar("incidente", i.datos())
    return i.datos()


@router.get("/estadisticas")
def estadisticas(_: Usuario = Depends(autoridad), db: Session = Depends(get_db)):
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    llenos = db.scalar(select(func.count()).select_from(Contenedor).where(Contenedor.llenado >= 80))
    return {
        "contenedores": db.scalar(select(func.count()).select_from(Contenedor)),
        "contenedores_llenos": llenos,
        "solicitudes_pendientes": db.scalar(select(func.count()).select_from(Solicitud).where(Solicitud.estado == "pendiente")),
        "recolecciones_hoy": db.scalar(select(func.count()).select_from(Recoleccion).where(Recoleccion.fecha >= hoy)),
        "incidentes_abiertos": db.scalar(select(func.count()).select_from(Incidente).where(Incidente.estado == "abierto")),
    }


# ─── Aplicación del personal de recolección ──────────────────────────────────
def _ruta_activa(db, u) -> Ruta | None:
    return db.scalar(select(Ruta).where(Ruta.recolector_id == u.id, Ruta.estado != "completada")
                     .order_by(Ruta.creada))


@router.get("/mi-ruta")
def mi_ruta(u: Usuario = Depends(recolector), db: Session = Depends(get_db)):
    r = _ruta_activa(db, u)
    return _ruta(db, r) if r else None


class Escaneo(BaseModel):
    codigo: str = Field(min_length=3, max_length=20)   # lo que leyó el QR, o lo que tipeó


@router.post("/recolecciones", status_code=201)
def recolectar(e: Escaneo, u: Usuario = Depends(recolector), db: Session = Depends(get_db)):
    """El QR del contenedor (o el código de la solicitud) confirma que el camión pasó por ahí."""
    r = _ruta_activa(db, u)
    if r is None:
        raise HTTPException(409, "No tenés una ruta asignada")
    codigo = e.codigo.strip().upper()
    paradas = [dict(x) for x in r.paradas]       # copia: el JSON cambiado tiene que reasignarse
    parada = next((x for x in paradas if x["codigo"] == codigo), None)
    if parada is None:
        raise HTTPException(404, f"{codigo} no está en tu ruta")
    if parada["hecha"]:
        raise HTTPException(409, f"{codigo} ya estaba registrado")
    parada["hecha"] = True
    r.paradas, r.estado = paradas, "en_curso"
    db.add(Recoleccion(ruta_id=r.id, recolector_id=u.id, tipo=parada["tipo"], punto_id=parada["id"]))
    if parada["tipo"] == "contenedor":
        c = db.get(Contenedor, parada["id"])
        c.llenado, c.actualizado = 0, datetime.now()
        eventos.publicar("contenedor", c.datos())
    else:
        s = db.get(Solicitud, parada["id"])
        s.estado = "recolectada"
        notificar(db, "residuos", "Retiramos tu residuo especial",
                  f"Solicitud #{s.id} ({s.tipo}) recolectada. ¡Gracias por separar!",
                  usuario_id=s.usuario_id, enlace="/vecino/residuos")
    if all(x["hecha"] for x in paradas):
        r.estado = "completada"
    db.commit()
    eventos.publicar("ruta", _ruta(db, r))
    return _ruta(db, r)


class NuevoIncidente(BaseModel):
    tipo: str = Field(pattern="^(contenedor_danado|acceso_bloqueado|derrame|desborde|otro)$")
    descripcion: str = Field(min_length=3, max_length=500)
    codigo: str | None = None


@router.post("/incidentes", status_code=201)
def incidente(i: NuevoIncidente, u: Usuario = Depends(requiere("recolector", "vecino")),
              db: Session = Depends(get_db)):
    c = None
    if i.codigo:
        c = db.scalar(select(Contenedor).where(Contenedor.codigo == i.codigo.strip().upper()))
        if c is None:
            raise HTTPException(404, "Contenedor inexistente")
        if i.tipo == "contenedor_danado":
            c.estado = "danado"
        elif i.tipo == "acceso_bloqueado":
            c.estado = "bloqueado"
        eventos.publicar("contenedor", c.datos())
    inc = Incidente(usuario_id=u.id, contenedor_id=c.id if c else None, tipo=i.tipo, descripcion=i.descripcion)
    db.add(inc)
    db.commit()
    eventos.publicar("incidente", inc.datos())
    return inc.datos()


@router.get("/contenedores/{codigo}")
def contenedor(codigo: str, _: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = db.scalar(select(Contenedor).where(Contenedor.codigo == codigo.upper()))
    if c is None:
        raise HTTPException(404, "Contenedor inexistente")
    return c.datos()
