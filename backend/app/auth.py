"""Login con token JWT. El rol viaja en el token y cada endpoint declara qué rol exige."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import Usuario

SECRETO = os.getenv("JWT_SECRET", "solo-para-desarrollo-cambiar-en-produccion")
_bearer = HTTPBearer(auto_error=False)


def hashear(clave: str) -> str:
    sal = secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal.encode(), 100_000).hex()
    return f"{sal}${h}"


def verificar(clave: str, guardado: str) -> bool:
    sal, h = guardado.split("$")
    otro = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal.encode(), 100_000).hex()
    return hmac.compare_digest(h, otro)


def emitir_token(u: Usuario) -> str:
    vence = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": str(u.id), "rol": u.rol, "exp": vence}, SECRETO, algorithm="HS256")


def usuario_de_token(token: str, db: Session) -> Usuario:
    try:
        datos = jwt.decode(token, SECRETO, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "La sesión venció; volvé a ingresar")
    u = db.get(Usuario, int(datos["sub"]))
    if u is None:
        raise HTTPException(401, "Usuario inexistente")
    # Devuelve la conexión al grupo ya: entre este paso y el endpoint, el pedido espera un hilo
    # libre, y no tiene que retener una conexión mientras espera (u sigue cargado: la sesión
    # no expira objetos al confirmar).
    db.commit()
    return u


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                   db: Session = Depends(get_db)) -> Usuario:
    if cred is None:
        raise HTTPException(401, "Falta iniciar sesión")
    return usuario_de_token(cred.credentials, db)


def requiere(*roles: str):
    """Dependencia que deja pasar sólo a los roles indicados."""
    def _check(u: Usuario = Depends(usuario_actual)) -> Usuario:
        if u.rol not in roles:
            raise HTTPException(403, f"Esta función es para: {', '.join(roles)}")
        return u
    return _check
