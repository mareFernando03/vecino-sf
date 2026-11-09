"""Datos de ejemplo. Todo es SIMULADO: las ubicaciones caen dentro del ejido de San Francisco
(Córdoba), pero ni las estaciones, ni los contenedores, ni las alarmas, ni los montos
corresponden a datos reales del municipio. Se regeneran igual en cada instalación
(semilla fija) para que las pruebas y las capturas sean reproducibles."""
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hashear
from .models import (Alarma, Cedulon, Contenedor, Estacion, Notificacion, Preferencias,
                     PuntoReciclaje, Reclamo, ReclamoEvento, Usuario, ZonaEstacionamiento)

CENTRO = (-31.4283, -62.0833)
BARRIOS = {          # centro aproximado de cinco zonas operativas (simuladas)
    "Centro": (-31.4283, -62.0833),
    "Norte": (-31.4145, -62.0840),
    "Sur": (-31.4440, -62.0860),
    "Este": (-31.4290, -62.0660),
    "Oeste": (-31.4300, -62.1010),
}

# Usuarios de demostración. Las claves están acá a propósito: es un prototipo.
USUARIOS = [
    ("30111222", "Ana Pereyra", "vecino", "vecino123", "Centro"),
    ("31222333", "Juan Gómez", "vecino", "vecino123", "Norte"),
    ("autoridad", "Dirección de Ambiente", "autoridad", "autoridad123", None),
    ("recolector1", "Carlos Díaz (camión 1)", "recolector", "recolector123", None),
    ("recolector2", "Marta Ruiz (camión 2)", "recolector", "recolector123", None),
]

CONTACTOS = [
    {"area": "Atención al vecino", "telefono": "+543564000100", "email": "vecino@vecino-sf.example",
     "whatsapp": "5493564000100", "horario": "Lunes a viernes 7 a 13"},
    {"area": "Dirección General Tributaria", "telefono": "+543564000200", "email": "tributaria@vecino-sf.example",
     "whatsapp": "5493564000200", "horario": "Lunes a viernes 7 a 13"},
    {"area": "Ambiente y residuos", "telefono": "+543564000300", "email": "ambiente@vecino-sf.example",
     "whatsapp": "5493564000300", "horario": "Lunes a sábado 6 a 14"},
    {"area": "Tránsito y estacionamiento", "telefono": "+543564000400", "email": "transito@vecino-sf.example",
     "whatsapp": "5493564000400", "horario": "Lunes a viernes 7 a 19"},
    {"area": "Guardia urbana (24 h)", "telefono": "+543564000500", "email": "guardia@vecino-sf.example",
     "whatsapp": "5493564000500", "horario": "Todos los días, 24 horas"},
]

HORARIOS = [
    {"barrio": b, "domiciliaria": h, "reciclables": r}
    for b, h, r in [
        ("Centro", "Lunes a sábado, 21 h", "Martes y viernes, 9 h"),
        ("Norte", "Lunes, miércoles y viernes, 20 h", "Jueves, 9 h"),
        ("Sur", "Martes, jueves y sábado, 20 h", "Lunes, 9 h"),
        ("Este", "Lunes, miércoles y viernes, 21 h", "Miércoles, 9 h"),
        ("Oeste", "Martes, jueves y sábado, 21 h", "Viernes, 9 h"),
    ]
]


def _cerca(rnd, centro, radio=0.008):
    return round(centro[0] + rnd.uniform(-radio, radio), 6), round(centro[1] + rnd.uniform(-radio, radio), 6)


def sembrar(db: Session):
    if db.scalar(select(Usuario).limit(1)):
        return
    rnd = random.Random(2026)
    us = {}
    for usuario, nombre, rol, clave, barrio in USUARIOS:
        u = Usuario(usuario=usuario, nombre=nombre, rol=rol, clave_hash=hashear(clave), barrio=barrio)
        db.add(u)
        us[usuario] = u
    db.flush()

    for i, (nombre, b) in enumerate([("Plaza central", "Centro"), ("Terminal", "Centro"),
                                     ("Parque norte", "Norte"), ("Polideportivo sur", "Sur"),
                                     ("Hospital", "Este"), ("Parque industrial", "Oeste"),
                                     ("Universidad", "Este"), ("Costanera", "Sur")]):
        lat, lng = _cerca(rnd, BARRIOS[b], 0.005)
        cap = rnd.choice([10, 12, 15])
        db.add(Estacion(nombre=f"Estación {nombre}", lat=lat, lng=lng, capacidad=cap, bicis=rnd.randint(0, cap)))

    hoy = date.today()
    for u in (us["30111222"], us["31222333"]):
        partida = f"{rnd.randint(10000, 99999)}"
        for k, (tributo, base) in enumerate([("Tasa a la propiedad", 18500), ("Contribución comercio e industria", 9200),
                                            ("Patente automotor", 31400)]):
            for m in range(3):
                venc = hoy.replace(day=10) + timedelta(days=30 * (m - 1))
                pagado = m == 0
                db.add(Cedulon(usuario_id=u.id, tributo=tributo, partida=f"{partida}-{k}",
                               periodo=venc.strftime("%m/%Y"), importe=round(base * rnd.uniform(0.95, 1.1), 2),
                               vencimiento=venc, estado="pagado" if pagado else "pendiente",
                               comprobante=f"SF-{rnd.randint(10**7, 10**8)}" if pagado else None,
                               medio="tarjeta" if pagado else None))

    r = Reclamo(usuario_id=us["30111222"].id, categoria="Alumbrado público",
                descripcion="Luminaria apagada en la esquina desde hace una semana.",
                direccion="Esquina de la plaza central", lat=CENTRO[0] + 0.001, lng=CENTRO[1] - 0.001,
                estado="en_curso")
    db.add(r)
    db.flush()
    db.add(ReclamoEvento(reclamo_id=r.id, estado="recibido", nota="Reclamo registrado."))
    db.add(ReclamoEvento(reclamo_id=r.id, estado="en_curso", nota="Asignado a la cuadrilla de alumbrado."))

    for b, c in BARRIOS.items():
        for n in range(2):
            lat, lng = _cerca(rnd, c, 0.006)
            db.add(Alarma(nombre=f"Alarma {b} {n + 1}", barrio=b, lat=lat, lng=lng, activa=False))

    def rect(lat, lng, dlat, dlng):
        return [[lat, lng], [lat, lng + dlng], [lat - dlat, lng + dlng], [lat - dlat, lng]]
    db.add(ZonaEstacionamiento(nombre="Zona A - Microcentro", tarifa_hora=900, horario="Lunes a viernes 8 a 20, sábados 8 a 13",
                               poligono=rect(-31.4255, -62.0870, 0.005, 0.007)))
    db.add(ZonaEstacionamiento(nombre="Zona B - Ampliación", tarifa_hora=600, horario="Lunes a viernes 8 a 13 y 16 a 20",
                               poligono=rect(-31.4305, -62.0870, 0.004, 0.007)))

    for i, (nombre, b, mats) in enumerate([
            ("Punto verde Plaza", "Centro", ["papel", "cartón", "plástico", "vidrio"]),
            ("Punto verde Norte", "Norte", ["plástico", "latas", "vidrio"]),
            ("Ecopunto Sur", "Sur", ["papel", "cartón", "plástico", "aceite usado"]),
            ("Centro de acopio Este", "Este", ["electrónicos", "pilas", "plástico"]),
            ("Planta de reciclado", "Oeste", ["todos los reciclables", "voluminosos", "neumáticos"])]):
        lat, lng = _cerca(rnd, BARRIOS[b], 0.004)
        db.add(PuntoReciclaje(nombre=nombre, lat=lat, lng=lng, materiales=mats,
                              horario="Lunes a sábado 8 a 18" if i < 4 else "Lunes a viernes 7 a 15"))

    n = 1
    for b, c in BARRIOS.items():
        for _ in range(6):
            lat, lng = _cerca(rnd, c, 0.007)
            db.add(Contenedor(codigo=f"SF-C-{n:03d}", barrio=b, tipo="reciclable" if n % 4 == 0 else "general",
                              lat=lat, lng=lng, llenado=rnd.randint(10, 95)))
            n += 1

    for u in (us["30111222"], us["31222333"]):
        db.add(Preferencias(usuario_id=u.id, tipos=["corte", "obra", "evento", "emergencia", "residuos",
                                                     "alarma", "tributaria", "reclamo", "estacionamiento"],
                            barrios=[], frecuencia="inmediata"))
    db.add(Notificacion(tipo="corte", titulo="Corte de agua programado",
                        cuerpo="Mañana de 8 a 12 en la zona Norte por obras en la red.", barrio="Norte",
                        enlace="/vecino/notificaciones"))
    db.add(Notificacion(tipo="residuos", titulo="Campaña de reciclaje de electrónicos",
                        cuerpo="Este sábado, en el Centro de acopio Este, recibimos electrónicos y pilas.",
                        enlace="/vecino/residuos"))
    db.commit()
