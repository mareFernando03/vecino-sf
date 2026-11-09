"""Servicios municipales del TP5: bicicletas, tributaria, reclamos, líneas de atención,
alarmas comunitarias y estacionamiento medido. Las APIs del municipio no son públicas,
así que cada servicio se simula acá con la forma que tendría su integración real."""
import os
import secrets
import uuid
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import eventos
from ..auth import requiere, usuario_actual
from ..db import get_db
from ..models import (Alarma, Cedulon, Estacion, Estacionamiento, Reclamo, ReclamoAdjunto,
                      ReclamoEvento, ReporteBici, Usuario, ZonaEstacionamiento)
from ..notificar import notificar
from ..rutas import distancia_km
from ..seed import CONTACTOS

router = APIRouter()
vecino = requiere("vecino")
ADJUNTOS = Path(os.getenv("UPLOAD_DIR", "adjuntos"))


# ─── 1. Bicicletas públicas ──────────────────────────────────────────────────
@router.get("/bicis/estaciones")
def estaciones(lat: float | None = None, lng: float | None = None, db: Session = Depends(get_db)):
    """Con lat/lng (la ubicación del vecino) vienen ordenadas de la más cercana a la más lejana."""
    lista = []
    for e in db.scalars(select(Estacion)).all():
        d = e.datos() | {"anclajes_libres": e.capacidad - e.bicis}
        if lat is not None and lng is not None:
            d["distancia_km"] = round(distancia_km((lat, lng), (e.lat, e.lng)), 2)
        lista.append(d)
    if lat is not None:
        lista.sort(key=lambda d: d["distancia_km"])
    return lista


class Reporte(BaseModel):
    estacion_id: int
    tipo: str = Field(pattern="^(bici|estacion)$")
    descripcion: str = Field(min_length=5, max_length=500)


@router.post("/bicis/reportes", status_code=201)
def reportar(r: Reporte, u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    if db.get(Estacion, r.estacion_id) is None:
        raise HTTPException(404, "Estación inexistente")
    rep = ReporteBici(usuario_id=u.id, **r.model_dump())
    db.add(rep)
    db.commit()
    return rep.datos()


# ─── 2. Dirección General Tributaria ─────────────────────────────────────────
@router.get("/tributaria/cedulones")
def cedulones(u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    """Estado de cuenta: obligaciones pendientes y vencidas, más el historial de pagos."""
    hoy = datetime.now().date()
    filas = db.scalars(select(Cedulon).where(Cedulon.usuario_id == u.id)
                       .order_by(Cedulon.vencimiento)).all()
    salida = []
    for c in filas:
        d = c.datos()
        d["vencido"] = c.estado == "pendiente" and c.vencimiento < hoy
        salida.append(d)
    deuda = sum(c.importe for c in filas if c.estado == "pendiente")
    return {"cedulones": salida, "deuda_total": round(deuda, 2)}


def _mi_cedulon(db, u, cid) -> Cedulon:
    c = db.get(Cedulon, cid)
    if c is None or c.usuario_id != u.id:
        raise HTTPException(404, "Cedulón inexistente")
    return c


@router.get("/tributaria/cedulones/{cid}/emitir", response_class=HTMLResponse)
def emitir(cid: int, u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    """El cedulón listo para imprimir o guardar como PDF desde el navegador."""
    c = _mi_cedulon(db, u, cid)
    codigo = f"{c.partida.replace('-', '')}{c.periodo.replace('/', '')}{int(c.importe * 100):010d}"
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>Cedulón {escape(c.partida)}</title>
<style>body{{font-family:Arial;max-width:640px;margin:24px auto}}td{{padding:4px 8px}}
.cod{{font-family:monospace;letter-spacing:2px;border:1px solid #000;padding:8px;text-align:center}}</style>
<h2>Municipalidad de San Francisco (simulación)</h2><h3>{escape(c.tributo)}</h3>
<table><tr><td>Contribuyente</td><td>{escape(u.nombre)} (DNI {escape(u.usuario)})</td></tr>
<tr><td>Partida</td><td>{escape(c.partida)}</td></tr><tr><td>Período</td><td>{escape(c.periodo)}</td></tr>
<tr><td>Vencimiento</td><td>{c.vencimiento:%d/%m/%Y}</td></tr>
<tr><td><b>Importe</b></td><td><b>$ {c.importe:,.2f}</b></td></tr>
<tr><td>Estado</td><td>{c.estado.upper()}</td></tr></table>
<p class="cod">{codigo}</p><p><small>Documento de prueba: no válido para pagar.</small></p>
<script>window.print && setTimeout(() => window.print(), 300)</script></html>"""


class Pago(BaseModel):
    medio: str = Field(pattern="^(tarjeta|debito|transferencia)$")


@router.post("/tributaria/cedulones/{cid}/pagar")
def pagar(cid: int, p: Pago, u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    """Pasarela de pago SIMULADA. En producción esto redirige a la pasarela (p. ej. un checkout
    de Mercado Pago) y el estado cambia cuando llega su webhook; nunca con un dato del cliente."""
    c = _mi_cedulon(db, u, cid)
    if c.estado == "pagado":
        raise HTTPException(409, "Ya estaba pagado")
    c.estado, c.medio, c.pagado_en = "pagado", p.medio, datetime.now()
    c.comprobante = f"SF-{secrets.randbelow(10**8):08d}"
    db.commit()
    return c.datos()


def recordar_vencimientos(db: Session, dias: int = 3) -> int:
    """Lo corre el simulador una vez por día: avisa los cedulones que vencen pronto."""
    hoy = datetime.now().date()
    n = 0
    for c in db.scalars(select(Cedulon).where(Cedulon.estado == "pendiente",
                                               Cedulon.vencimiento >= hoy,
                                               Cedulon.vencimiento <= hoy + timedelta(days=dias))).all():
        notificar(db, "tributaria", f"Vence {c.tributo}",
                  f"El período {c.periodo} vence el {c.vencimiento:%d/%m} (${c.importe:,.2f}).",
                  usuario_id=c.usuario_id, enlace="/vecino/tributaria")
        n += 1
    return n


# ─── 3. Centro de reclamos ───────────────────────────────────────────────────
CATEGORIAS = ["Alumbrado público", "Bache o calle", "Arbolado", "Residuos y limpieza",
              "Agua y cloacas", "Tránsito y señalización", "Otro"]


@router.get("/reclamos/categorias")
def categorias():
    return CATEGORIAS


# El tipo se deduce de los primeros bytes del archivo, no del encabezado que manda el cliente,
# y la extensión con que se guarda sale de esta tabla: nunca del nombre que subió el usuario.
FIRMAS = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png", b"%PDF-": ".pdf"}


def tipo_real(contenido: bytes) -> str | None:
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return ".webp"
    return next((ext for firma, ext in FIRMAS.items() if contenido.startswith(firma)), None)


@router.post("/reclamos", status_code=201)
async def crear_reclamo(categoria: str = Form(...), descripcion: str = Form(..., min_length=10),
                        direccion: str = Form(...), lat: float | None = Form(None),
                        lng: float | None = Form(None), archivos: list[UploadFile] = File(default=[]),
                        u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    if categoria not in CATEGORIAS:
        raise HTTPException(422, "Categoría inválida")
    if len(archivos) > 4:
        raise HTTPException(422, "Hasta 4 adjuntos")
    r = Reclamo(usuario_id=u.id, categoria=categoria, descripcion=descripcion,
                direccion=direccion, lat=lat, lng=lng)
    db.add(r)
    db.flush()
    ADJUNTOS.mkdir(parents=True, exist_ok=True)
    for a in archivos:
        contenido = await a.read()
        if len(contenido) > 5 * 1024 * 1024:
            raise HTTPException(413, f"{a.filename}: supera 5 MB")
        ext = tipo_real(contenido)
        if ext is None:
            raise HTTPException(415, f"{a.filename}: sólo fotos (JPG, PNG, WebP) o PDF")
        nombre = f"{uuid.uuid4().hex}{ext}"
        (ADJUNTOS / nombre).write_bytes(contenido)
        db.add(ReclamoAdjunto(reclamo_id=r.id, nombre=a.filename or nombre, archivo=nombre))
    db.add(ReclamoEvento(reclamo_id=r.id, estado="recibido", nota="Reclamo registrado."))
    db.commit()
    eventos.publicar("reclamo", {"id": r.id, "estado": r.estado})
    return _detalle(db, r)


def _detalle(db, r: Reclamo):
    d = r.datos()
    d["adjuntos"] = [{"nombre": a.nombre, "url": f"/api/adjuntos/{a.archivo}"} for a in
                     db.scalars(select(ReclamoAdjunto).where(ReclamoAdjunto.reclamo_id == r.id)).all()]
    d["eventos"] = [e.datos() for e in db.scalars(select(ReclamoEvento).where(
        ReclamoEvento.reclamo_id == r.id).order_by(ReclamoEvento.fecha)).all()]
    return d


@router.get("/reclamos")
def mis_reclamos(q: str | None = None, estado: str | None = None,
                 u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """El vecino ve los suyos; la autoridad, todos. Búsqueda por texto y por estado."""
    s = select(Reclamo).order_by(Reclamo.creado.desc())
    if u.rol == "vecino":
        s = s.where(Reclamo.usuario_id == u.id)
    if q:
        patron = f"%{q}%"
        s = s.where(or_(Reclamo.descripcion.ilike(patron), Reclamo.categoria.ilike(patron),
                        Reclamo.direccion.ilike(patron)))
    if estado:
        s = s.where(Reclamo.estado == estado)
    return [_detalle(db, r) for r in db.scalars(s).all()]


@router.get("/reclamos/{rid}")
def ver_reclamo(rid: int, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = db.get(Reclamo, rid)
    if r is None or (u.rol == "vecino" and r.usuario_id != u.id):
        raise HTTPException(404, "Reclamo inexistente")
    return _detalle(db, r)


class CambioEstado(BaseModel):
    estado: str = Field(pattern="^(recibido|en_curso|resuelto)$")
    nota: str = Field(min_length=3)


@router.patch("/reclamos/{rid}")
def actualizar_reclamo(rid: int, c: CambioEstado, _: Usuario = Depends(requiere("autoridad")),
                       db: Session = Depends(get_db)):
    r = db.get(Reclamo, rid)
    if r is None:
        raise HTTPException(404, "Reclamo inexistente")
    r.estado = c.estado
    db.add(ReclamoEvento(reclamo_id=r.id, estado=c.estado, nota=c.nota))
    db.commit()
    notificar(db, "reclamo", f"Tu reclamo #{r.id} cambió a «{c.estado.replace('_', ' ')}»", c.nota,
              usuario_id=r.usuario_id, enlace=f"/vecino/reclamos/{r.id}")
    return _detalle(db, r)


# ─── 4. Líneas de atención al vecino ─────────────────────────────────────────
@router.get("/contactos")
def contactos():
    return CONTACTOS


# ─── 5. Alarmas comunitarias ─────────────────────────────────────────────────
@router.get("/alarmas")
def alarmas(db: Session = Depends(get_db)):
    return [a.datos() for a in db.scalars(select(Alarma)).all()]


class EstadoAlarma(BaseModel):
    activa: bool


def cambiar_alarma(db: Session, a: Alarma, activa: bool):
    a.activa, a.actualizada = activa, datetime.now()
    db.commit()
    eventos.publicar("alarma", a.datos())
    if activa:
        notificar(db, "alarma", f"Alarma activada: {a.nombre}",
                  f"Se activó la alarma comunitaria de la zona {a.barrio}.",
                  barrio=a.barrio, enlace="/vecino/alarmas")


@router.patch("/alarmas/{aid}")
def activar(aid: int, e: EstadoAlarma, _: Usuario = Depends(requiere("autoridad")),
            db: Session = Depends(get_db)):
    """En la realidad la activa el pulsador del vecino o la central de monitoreo. En el prototipo
    la central es el rol autoridad: un vecino no puede disparar una alarma de toda la zona."""
    a = db.get(Alarma, aid)
    if a is None:
        raise HTTPException(404, "Alarma inexistente")
    cambiar_alarma(db, a, e.activa)
    return a.datos()


# ─── 6. Estacionamiento medido ───────────────────────────────────────────────
@router.get("/estacionamiento/zonas")
def zonas(db: Session = Depends(get_db)):
    return [z.datos() for z in db.scalars(select(ZonaEstacionamiento)).all()]


class Inicio(BaseModel):
    zona_id: int
    patente: str = Field(pattern=r"^([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$")
    minutos: int = Field(ge=15, le=240)
    medio: str = Field(pattern="^(tarjeta|debito|transferencia)$")


def _cobrar(e: Estacionamiento, medio: str):
    """Pasarela SIMULADA, igual que en Tributaria: aprueba y emite un comprobante. En producción
    el estacionamiento queda activo cuando la pasarela confirma el pago, no antes."""
    e.medio, e.comprobante = medio, f"EM-{secrets.randbelow(10**8):08d}"


def _activo(db, u):
    return db.scalar(select(Estacionamiento).where(Estacionamiento.usuario_id == u.id,
                                                   Estacionamiento.fin > datetime.now()))


@router.get("/estacionamiento/activo")
def activo(u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    e = _activo(db, u)
    return e.datos() if e else None


@router.post("/estacionamiento", status_code=201)
def estacionar(i: Inicio, u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    z = db.get(ZonaEstacionamiento, i.zona_id)
    if z is None:
        raise HTTPException(404, "Zona inexistente")
    if _activo(db, u):
        raise HTTPException(409, "Ya tenés un estacionamiento activo: extendelo")
    ahora = datetime.now()
    e = Estacionamiento(usuario_id=u.id, zona_id=z.id, patente=i.patente, inicio=ahora,
                        fin=ahora + timedelta(minutes=i.minutos),
                        importe=round(z.tarifa_hora * i.minutos / 60, 2))
    _cobrar(e, i.medio)
    db.add(e)
    db.commit()
    return e.datos()


class Extension(BaseModel):
    minutos: int = Field(ge=15, le=120)
    medio: str = Field(pattern="^(tarjeta|debito|transferencia)$")


@router.post("/estacionamiento/extender")
def extender(x: Extension, u: Usuario = Depends(vecino), db: Session = Depends(get_db)):
    e = _activo(db, u)
    if e is None:
        raise HTTPException(404, "No hay estacionamiento activo")
    z = db.get(ZonaEstacionamiento, e.zona_id)
    e.fin += timedelta(minutes=x.minutos)
    e.importe = round(e.importe + z.tarifa_hora * x.minutos / 60, 2)
    e.avisado = False
    _cobrar(e, x.medio)          # cada extensión es un cobro nuevo, con su comprobante
    db.commit()
    return e.datos()


def avisar_vencimientos_estacionamiento(db: Session, minutos: int = 10) -> int:
    """El simulador lo corre cada minuto: avisa por push cuando faltan 10 minutos."""
    ahora = datetime.now()
    n = 0
    for e in db.scalars(select(Estacionamiento).where(Estacionamiento.avisado.is_(False),
                                                      Estacionamiento.fin > ahora,
                                                      Estacionamiento.fin <= ahora + timedelta(minutes=minutos))).all():
        e.avisado = True
        db.commit()
        notificar(db, "estacionamiento", "Tu estacionamiento está por vencer",
                  f"Patente {e.patente}: vence a las {e.fin:%H:%M}. Podés extenderlo desde la app.",
                  usuario_id=e.usuario_id, enlace="/vecino/estacionamiento")
        n += 1
    return n
