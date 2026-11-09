"""Un único punto para avisarle algo al vecino.

notificar() guarda la notificación (el historial), la publica en tiempo real (la ven
quienes tienen la app abierta) y manda un push web a quienes la tienen cerrada. Respeta
las preferencias de cada usuario: tipos de aviso y zonas de interés.
"""
import json
import logging
import os
from pathlib import Path

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import eventos
from .models import Notificacion, Preferencias, SuscripcionPush, Usuario

log = logging.getLogger("vecino.push")
TIPOS = ["corte", "obra", "evento", "emergencia", "residuos", "alarma",
         "tributaria", "reclamo", "estacionamiento"]


def _claves_vapid():
    """VAPID: el par de claves con que el servidor firma sus push. En Kubernetes vienen de
    un Secret; en desarrollo se generan una vez y se guardan en vapid.json."""
    pub, priv = os.getenv("VAPID_PUBLIC"), os.getenv("VAPID_PRIVATE")
    if pub and priv:
        return pub, priv
    archivo = Path(os.getenv("VAPID_FILE", "vapid.json"))
    import base64
    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    priv = base64.urlsafe_b64encode(k.private_numbers().private_value.to_bytes(32, "big")).rstrip(b"=").decode()
    pub = base64.urlsafe_b64encode(k.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).rstrip(b"=").decode()
    try:
        # "x" = crear sólo si no existe: si varias réplicas arrancan juntas, gana una
        # y las demás leen sus claves (todas tienen que firmar con el mismo par).
        with open(archivo, "x") as f:
            f.write(json.dumps({"public": pub, "private": priv}))
        return pub, priv
    except FileExistsError:
        for _ in range(50):
            try:
                d = json.loads(archivo.read_text())
                return d["public"], d["private"]
            except (ValueError, KeyError):
                time.sleep(0.1)       # la otra réplica todavía está escribiendo
        raise


VAPID_PUBLIC, VAPID_PRIVATE = _claves_vapid()
VAPID_CONTACTO = os.getenv("VAPID_CONTACTO", "mailto:sistemas@vecino-sf.example")


def quiere(prefs: Preferencias | None, tipo: str, barrio: str | None) -> bool:
    if tipo == "emergencia":                       # las emergencias no se pueden silenciar
        return True
    if prefs is None:
        return True
    if tipo not in prefs.tipos:
        return False
    return barrio is None or not prefs.barrios or barrio in prefs.barrios


def enviar_push(db: Session, usuario_id: int, datos: dict) -> int:
    enviados = 0
    for s in db.scalars(select(SuscripcionPush).where(SuscripcionPush.usuario_id == usuario_id)).all():
        try:
            webpush({"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}},
                    json.dumps(datos), vapid_private_key=VAPID_PRIVATE,
                    vapid_claims={"sub": VAPID_CONTACTO}, timeout=5)
            enviados += 1
        except WebPushException as e:
            if e.response is not None and e.response.status_code in (404, 410):
                db.delete(s)                       # el navegador dio de baja la suscripción
            else:
                log.warning("push falló: %s", e)
        except Exception as e:                      # sin red, etc.: el aviso igual queda en el historial
            log.warning("push falló: %s", e)
    return enviados


def notificar(db: Session, tipo: str, titulo: str, cuerpo: str, *, usuario_id: int | None = None,
              barrio: str | None = None, enlace: str | None = None) -> Notificacion:
    n = Notificacion(usuario_id=usuario_id, tipo=tipo, titulo=titulo, cuerpo=cuerpo,
                     barrio=barrio, enlace=enlace)
    db.add(n)
    db.commit()
    datos = {"id": n.id, "tipo": tipo, "titulo": titulo, "cuerpo": cuerpo,
             "enlace": enlace, "barrio": barrio, "usuario_id": usuario_id}
    eventos.publicar("notificacion", datos)

    if usuario_id is not None:
        destinatarios = [db.get(Usuario, usuario_id)]
    else:
        destinatarios = db.scalars(select(Usuario).where(Usuario.rol == "vecino")).all()
    for u in destinatarios:
        prefs = db.get(Preferencias, u.id)
        if quiere(prefs, tipo, barrio) and (prefs is None or prefs.frecuencia == "inmediata"
                                            or tipo == "emergencia"):
            enviar_push(db, u.id, datos)
    db.commit()
    return n
