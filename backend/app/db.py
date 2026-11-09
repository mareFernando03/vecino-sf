"""Conexión a la base. En desarrollo es un archivo SQLite; en Docker y Kubernetes,
PostgreSQL. Lo único que cambia es la variable DATABASE_URL."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vecino.db")

_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# Presupuesto de conexiones: réplicas máximas × procesos por réplica × (POOL + OVERFLOW) tiene
# que entrar en el max_connections de PostgreSQL. Cada contenedor corre UN proceso (Dockerfile),
# así que con el HPA en 20 réplicas: 20 × 1 × (4 + 2) = 120 < 150.
# Sin este tope, la prueba de autoescalado agotó la base ("too many clients already").
engine = create_engine(DATABASE_URL, connect_args=_args, pool_pre_ping=True,
                       **({} if DATABASE_URL.startswith("sqlite") else {
                           "pool_size": int(os.getenv("DB_POOL", "5")),
                           "max_overflow": int(os.getenv("DB_OVERFLOW", "10")),
                           "pool_timeout": 10}))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    def datos(self) -> dict:
        """La fila como diccionario, para devolverla como JSON."""
        return {c.key: getattr(self, c.key) for c in self.__table__.columns}


async def get_db():
    """Una sesión por pedido. Es async a propósito: así FastAPI la abre y la cierra en el bucle
    de eventos y no en el grupo de hilos de los endpoints. Con una dependencia síncrona, bajo
    carga el cierre esperaba un hilo libre detrás de pedidos que a su vez esperaban una conexión:
    las conexiones quedaban tomadas sin uso y el servicio se trababa (docs/prueba-k8s-*.log)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def preparar_base():
    """Crea las tablas y carga los datos de ejemplo una sola vez. Con varias réplicas
    arrancando a la vez, en PostgreSQL un candado de la base evita que lo hagan dos juntas."""
    import time

    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from .seed import sembrar
    for intento in range(30):          # la base puede tardar en estar lista al arrancar todo junto
        try:
            with engine.connect():
                break
        except OperationalError:
            time.sleep(2)
    with engine.begin() as con:
        if engine.dialect.name == "postgresql":
            con.execute(text("SELECT pg_advisory_xact_lock(2026)"))
        Base.metadata.create_all(con)
        with SessionLocal(bind=con) as db:
            sembrar(db)
