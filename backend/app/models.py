"""Tablas. Una sección por servicio municipal y una por el sistema de residuos."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def ahora():
    return datetime.now()


# ─── Usuarios ────────────────────────────────────────────────────────────────
class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(40), unique=True)   # DNI para vecinos
    nombre: Mapped[str] = mapped_column(String(80))
    rol: Mapped[str] = mapped_column(String(15))                    # vecino | autoridad | recolector
    clave_hash: Mapped[str] = mapped_column(String(200))
    barrio: Mapped[str | None] = mapped_column(String(40))


# ─── 1. Bicicletas públicas ──────────────────────────────────────────────────
class Estacion(Base):
    __tablename__ = "estaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    capacidad: Mapped[int] = mapped_column(Integer)
    bicis: Mapped[int] = mapped_column(Integer)                     # anclajes libres = capacidad - bicis


class ReporteBici(Base):
    __tablename__ = "reportes_bici"
    id: Mapped[int] = mapped_column(primary_key=True)
    estacion_id: Mapped[int] = mapped_column(ForeignKey("estaciones.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(30))                   # bici | estacion
    descripcion: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


# ─── 2. Dirección General Tributaria ─────────────────────────────────────────
class Cedulon(Base):
    __tablename__ = "cedulones"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tributo: Mapped[str] = mapped_column(String(60))
    partida: Mapped[str] = mapped_column(String(20))
    periodo: Mapped[str] = mapped_column(String(10))
    importe: Mapped[float] = mapped_column(Float)
    vencimiento: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")   # pendiente | pagado
    pagado_en: Mapped[datetime | None] = mapped_column(DateTime)
    comprobante: Mapped[str | None] = mapped_column(String(30))
    medio: Mapped[str | None] = mapped_column(String(20))


# ─── 3. Centro de reclamos ───────────────────────────────────────────────────
class Reclamo(Base):
    __tablename__ = "reclamos"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    categoria: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str] = mapped_column(Text)
    direccion: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    estado: Mapped[str] = mapped_column(String(15), default="recibido")    # recibido | en_curso | resuelto
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class ReclamoAdjunto(Base):
    __tablename__ = "reclamo_adjuntos"
    id: Mapped[int] = mapped_column(primary_key=True)
    reclamo_id: Mapped[int] = mapped_column(ForeignKey("reclamos.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    archivo: Mapped[str] = mapped_column(String(200))


class ReclamoEvento(Base):
    """Historial de estados: es lo que el vecino ve como 'seguimiento'."""
    __tablename__ = "reclamo_eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    reclamo_id: Mapped[int] = mapped_column(ForeignKey("reclamos.id"))
    estado: Mapped[str] = mapped_column(String(15))
    nota: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


# ─── 5. Alarmas comunitarias ─────────────────────────────────────────────────
class Alarma(Base):
    __tablename__ = "alarmas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    barrio: Mapped[str] = mapped_column(String(40))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    activa: Mapped[bool] = mapped_column(Boolean, default=False)
    actualizada: Mapped[datetime] = mapped_column(DateTime, default=ahora)


# ─── 6. Estacionamiento medido ───────────────────────────────────────────────
class ZonaEstacionamiento(Base):
    __tablename__ = "zonas_estacionamiento"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    tarifa_hora: Mapped[float] = mapped_column(Float)
    horario: Mapped[str] = mapped_column(String(80))
    poligono: Mapped[list] = mapped_column(JSON)                    # [[lat, lng], ...]


class Estacionamiento(Base):
    __tablename__ = "estacionamientos"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    zona_id: Mapped[int] = mapped_column(ForeignKey("zonas_estacionamiento.id"))
    patente: Mapped[str] = mapped_column(String(10))
    inicio: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fin: Mapped[datetime] = mapped_column(DateTime)
    importe: Mapped[float] = mapped_column(Float)
    avisado: Mapped[bool] = mapped_column(Boolean, default=False)   # ya se mandó el aviso de vencimiento
    medio: Mapped[str | None] = mapped_column(String(20))           # pago simulado
    comprobante: Mapped[str | None] = mapped_column(String(30))     # del último cobro


# ─── 7. Notificaciones al vecino ─────────────────────────────────────────────
class Notificacion(Base):
    __tablename__ = "notificaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))  # None = para todos
    tipo: Mapped[str] = mapped_column(String(20))   # corte | obra | evento | emergencia | residuos | alarma | tributaria | reclamo | estacionamiento
    titulo: Mapped[str] = mapped_column(String(120))
    cuerpo: Mapped[str] = mapped_column(Text)
    enlace: Mapped[str | None] = mapped_column(String(200))
    barrio: Mapped[str | None] = mapped_column(String(40))          # None = toda la ciudad
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Preferencias(Base):
    __tablename__ = "preferencias"
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    tipos: Mapped[list] = mapped_column(JSON)       # tipos que quiere recibir
    barrios: Mapped[list] = mapped_column(JSON)     # zonas de interés; vacío = toda la ciudad
    frecuencia: Mapped[str] = mapped_column(String(15), default="inmediata")   # inmediata | resumen_diario


class SuscripcionPush(Base):
    __tablename__ = "suscripciones_push"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))


# ─── Residuos (caso Geo Maps) ────────────────────────────────────────────────
class PuntoReciclaje(Base):
    __tablename__ = "puntos_reciclaje"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    materiales: Mapped[list] = mapped_column(JSON)
    horario: Mapped[str] = mapped_column(String(80))


class RegistroResiduo(Base):
    __tablename__ = "registros_residuo"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    categoria: Mapped[str] = mapped_column(String(20))   # organico | reciclable | voluminoso | peligroso | otros
    cantidad: Mapped[float] = mapped_column(Float)
    unidad: Mapped[str] = mapped_column(String(10))      # kg | bolsas | unidades
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Solicitud(Base):
    """Pedido de recolección de un residuo especial en el domicilio del vecino."""
    __tablename__ = "solicitudes"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(20))        # reciclable | voluminoso | peligroso
    descripcion: Mapped[str] = mapped_column(Text)
    direccion: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    estado: Mapped[str] = mapped_column(String(15), default="pendiente")   # pendiente | asignada | recolectada
    ruta_id: Mapped[int | None] = mapped_column(ForeignKey("rutas.id"))
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Contenedor(Base):
    __tablename__ = "contenedores"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)   # lo que lleva el QR pegado
    barrio: Mapped[str] = mapped_column(String(40))
    tipo: Mapped[str] = mapped_column(String(20))                  # general | reciclable
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    llenado: Mapped[int] = mapped_column(Integer, default=0)       # porcentaje que informa el sensor
    estado: Mapped[str] = mapped_column(String(15), default="ok")  # ok | danado | bloqueado
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Ruta(Base):
    __tablename__ = "rutas"
    id: Mapped[int] = mapped_column(primary_key=True)
    recolector_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    estado: Mapped[str] = mapped_column(String(15), default="asignada")   # asignada | en_curso | completada
    paradas: Mapped[list] = mapped_column(JSON)     # [{"tipo": "contenedor"|"solicitud", "id", "lat", "lng", "hecha"}]
    distancia_km: Mapped[float] = mapped_column(Float)
    geometria: Mapped[list] = mapped_column(JSON)   # [[lat, lng], ...] para dibujar
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Recoleccion(Base):
    __tablename__ = "recolecciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    ruta_id: Mapped[int] = mapped_column(ForeignKey("rutas.id"))
    recolector_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(15))
    punto_id: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Incidente(Base):
    __tablename__ = "incidentes"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    contenedor_id: Mapped[int | None] = mapped_column(ForeignKey("contenedores.id"))
    tipo: Mapped[str] = mapped_column(String(30))       # contenedor_danado | acceso_bloqueado | derrame | otro
    descripcion: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(12), default="abierto")    # abierto | resuelto
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
