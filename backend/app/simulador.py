"""Simula los sensores y las tareas programadas que en producción vendrían de afuera:

- disponibilidad de bicicletas (en la realidad, las estaciones informan por IoT);
- llenado de contenedores (sensores ultrasónicos);
- avisos de vencimiento de estacionamiento (cada minuto) y de cedulones (una vez por día).

Corre como un proceso aparte (`python -m app.simulador`): en Kubernetes es un Deployment de
una sola réplica, para que el trabajo no se repita en cada réplica de la API.
"""
import logging
import os
import random
import time
from datetime import date, datetime

from sqlalchemy import select

from . import eventos
from .db import SessionLocal, preparar_base
from .models import Contenedor, Estacion
from .routers.servicios import avisar_vencimientos_estacionamiento, recordar_vencimientos

log = logging.getLogger("vecino.simulador")
INTERVALO = int(os.getenv("SIMULADOR_INTERVALO", "20"))


def paso(db, rnd: random.Random):
    for e in db.scalars(select(Estacion)).all():
        if rnd.random() < 0.4:
            e.bicis = max(0, min(e.capacidad, e.bicis + rnd.choice([-1, 1])))
            eventos.publicar("estacion", e.datos() | {"anclajes_libres": e.capacidad - e.bicis})
    for c in db.scalars(select(Contenedor)).all():
        if c.llenado < 100 and rnd.random() < 0.3:
            c.llenado = min(100, c.llenado + rnd.randint(1, 4))
            c.actualizado = datetime.now()
            eventos.publicar("contenedor", c.datos())
    db.commit()
    avisar_vencimientos_estacionamiento(db)


def main(preparar=True):
    logging.basicConfig(level=logging.INFO)
    if preparar:                      # proceso aparte: crea tablas y se conecta a Redis
        preparar_base()
        eventos.conectar_publicador()
    rnd, ultimo_dia = random.Random(), None
    while True:
        with SessionLocal() as db:
            paso(db, rnd)
            if ultimo_dia != date.today():
                n = recordar_vencimientos(db)
                log.info("recordatorios de vencimiento enviados: %s", n)
                ultimo_dia = date.today()
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
