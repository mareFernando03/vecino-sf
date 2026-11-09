"""Pruebas de punta a punta de la API, con una base SQLite temporal.

    cd backend && python -m pytest -q
"""
import os
import random
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ.update(DATABASE_URL=f"sqlite:///{TMP / 'test.db'}", UPLOAD_DIR=str(TMP / "adj"),
                  VAPID_FILE=str(TMP / "vapid.json"), OSRM_URL="http://127.0.0.1:9")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import rutas  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Estacionamiento  # noqa: E402
from app.routers.servicios import avisar_vencimientos_estacionamiento, recordar_vencimientos  # noqa: E402


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as cliente:
        yield cliente


def h(c, usuario, clave):
    r = c.post("/api/auth/login", json={"usuario": usuario, "clave": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def ana(c):
    return h(c, "30111222", "vecino123")


@pytest.fixture(scope="module")
def autoridad(c):
    return h(c, "autoridad", "autoridad123")


@pytest.fixture(scope="module")
def rec1(c):
    return h(c, "recolector1", "recolector123")


# ─── Sesión y permisos ───────────────────────────────────────────────────────
def test_login_incorrecto(c):
    assert c.post("/api/auth/login", json={"usuario": "30111222", "clave": "mal"}).status_code == 401


def test_sin_token_401_y_rol_equivocado_403(c, rec1):
    assert c.get("/api/tributaria/cedulones").status_code == 401
    assert c.get("/api/tributaria/cedulones", headers=rec1).status_code == 403
    assert c.post("/api/residuos/rutas", json={"recolector_id": 1}, headers=rec1).status_code == 403


def test_salud_y_metricas(c):
    assert c.get("/salud").json()["ok"] is True
    m = c.get("/metrics").text
    assert "http_requests_total" in m and "vecino_conexiones_sse" in m


# ─── 1. Bicicletas ───────────────────────────────────────────────────────────
def test_estaciones_ordenadas_por_cercania(c, ana):
    lista = c.get("/api/bicis/estaciones", params={"lat": -31.4145, "lng": -62.0840}).json()
    d = [e["distancia_km"] for e in lista]
    assert d == sorted(d) and len(lista) == 8
    assert all(e["bicis"] + e["anclajes_libres"] == e["capacidad"] for e in lista)
    r = c.post("/api/bicis/reportes", headers=ana,
               json={"estacion_id": lista[0]["id"], "tipo": "bici", "descripcion": "Cadena cortada"})
    assert r.status_code == 201


# ─── 2. Tributaria ───────────────────────────────────────────────────────────
def test_tributaria_consulta_emite_y_paga(c, ana):
    cuenta = c.get("/api/tributaria/cedulones", headers=ana).json()
    pend = [x for x in cuenta["cedulones"] if x["estado"] == "pendiente"]
    assert pend and cuenta["deuda_total"] == pytest.approx(sum(x["importe"] for x in pend), abs=0.01)
    html = c.get(f"/api/tributaria/cedulones/{pend[0]['id']}/emitir", headers=ana).text
    assert pend[0]["partida"] in html and "Importe" in html
    pago = c.post(f"/api/tributaria/cedulones/{pend[0]['id']}/pagar", headers=ana, json={"medio": "tarjeta"})
    assert pago.json()["estado"] == "pagado" and pago.json()["comprobante"].startswith("SF-")
    assert c.post(f"/api/tributaria/cedulones/{pend[0]['id']}/pagar", headers=ana,
                  json={"medio": "tarjeta"}).status_code == 409


def test_no_ve_cedulones_ajenos(c):
    juan = h(c, "31222333", "vecino123")
    ajeno = c.get("/api/tributaria/cedulones", headers=h(c, "30111222", "vecino123")).json()["cedulones"][0]
    assert c.get(f"/api/tributaria/cedulones/{ajeno['id']}/emitir", headers=juan).status_code == 404


def test_recordatorio_de_vencimiento(c, ana):
    with SessionLocal() as db:
        n = recordar_vencimientos(db, dias=60)
    assert n >= 1
    tipos = [x["tipo"] for x in c.get("/api/notificaciones", headers=ana).json()]
    assert "tributaria" in tipos


# ─── 3. Reclamos ─────────────────────────────────────────────────────────────
def test_reclamo_con_foto_y_seguimiento(c, ana, autoridad):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = c.post("/api/reclamos", headers=ana,
               data={"categoria": "Bache o calle", "descripcion": "Pozo grande frente a la escuela",
                     "direccion": "Calle de prueba 123", "lat": "-31.43", "lng": "-62.08"},
               files=[("archivos", ("pozo.png", png, "image/png"))])
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["adjuntos"][0]["nombre"] == "pozo.png"
    assert c.get(rec["adjuntos"][0]["url"]).content == png
    c.patch(f"/api/reclamos/{rec['id']}", headers=autoridad, json={"estado": "en_curso", "nota": "Cuadrilla asignada"})
    det = c.get(f"/api/reclamos/{rec['id']}", headers=ana).json()
    assert det["estado"] == "en_curso" and [e["estado"] for e in det["eventos"]] == ["recibido", "en_curso"]
    assert c.get("/api/reclamos", params={"q": "escuela"}, headers=ana).json()[0]["id"] == rec["id"]
    avisos = c.get("/api/notificaciones", headers=ana).json()
    assert any(a["tipo"] == "reclamo" and str(rec["id"]) in a["titulo"] for a in avisos)


def test_reclamo_rechaza_ejecutable_y_tipo_falsificado(c, ana):
    def subir(nombre, contenido, tipo):
        return c.post("/api/reclamos", headers=ana,
                      data={"categoria": "Otro", "descripcion": "Adjunto no permitido", "direccion": "x"},
                      files=[("archivos", (nombre, contenido, tipo))]).status_code
    assert subir("virus.exe", b"MZ", "application/octet-stream") == 415
    # Una página HTML que se declara imagen: el tipo se mira en el contenido, no en el encabezado.
    assert subir("foto.html", b"<script>alert(1)</script>", "image/png") == 415


def test_adjunto_se_guarda_con_extension_propia_y_nosniff(c, ana):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
    r = c.post("/api/reclamos", headers=ana,
               data={"categoria": "Otro", "descripcion": "Foto con nombre raro", "direccion": "x"},
               files=[("archivos", ("foto.html", png, "image/png"))]).json()
    url = r["adjuntos"][0]["url"]
    assert url.endswith(".png")                                  # no conserva ".html"
    assert c.get(url).headers["x-content-type-options"] == "nosniff"


# ─── 4 y 5. Contactos y alarmas ──────────────────────────────────────────────
def test_contactos(c):
    cs = c.get("/api/contactos").json()
    assert all(x["telefono"].startswith("+54") and "@" in x["email"] and x["whatsapp"] for x in cs)


def test_alarma_avisa_solo_a_quien_sigue_esa_zona(c, ana, autoridad):
    juan = h(c, "31222333", "vecino123")
    c.put("/api/notificaciones/preferencias", headers=juan,
          json={"tipos": ["alarma"], "barrios": ["Norte"], "frecuencia": "inmediata"})
    sur = next(a for a in c.get("/api/alarmas").json() if a["barrio"] == "Sur")
    assert c.patch(f"/api/alarmas/{sur['id']}", headers=ana, json={"activa": True}).status_code == 403
    c.patch(f"/api/alarmas/{sur['id']}", headers=autoridad, json={"activa": True})   # la central
    assert any(a["id"] == sur["id"] and a["activa"] for a in c.get("/api/alarmas").json())
    titulos_juan = [n["titulo"] for n in c.get("/api/notificaciones", headers=juan).json()]
    titulos_ana = [n["titulo"] for n in c.get("/api/notificaciones", headers=ana).json()]
    assert any(sur["nombre"] in t for t in titulos_ana)        # Ana sigue toda la ciudad
    assert not any(sur["nombre"] in t for t in titulos_juan)   # Juan sólo sigue el Norte


# ─── 6. Estacionamiento ──────────────────────────────────────────────────────
def test_estacionamiento_iniciar_extender_y_aviso(c, ana):
    z = c.get("/api/estacionamiento/zonas").json()[0]
    assert c.post("/api/estacionamiento", headers=ana, json={"zona_id": z["id"], "patente": "abc123",
                                                              "minutos": 60, "medio": "debito"}).status_code == 422
    e = c.post("/api/estacionamiento", headers=ana,
               json={"zona_id": z["id"], "patente": "AB123CD", "minutos": 60, "medio": "debito"}).json()
    assert e["importe"] == z["tarifa_hora"]
    assert e["medio"] == "debito" and e["comprobante"].startswith("EM-")
    assert c.post("/api/estacionamiento", headers=ana,
                  json={"zona_id": z["id"], "patente": "AB123CD", "minutos": 30, "medio": "debito"}).status_code == 409
    e2 = c.post("/api/estacionamiento/extender", headers=ana, json={"minutos": 30, "medio": "debito"}).json()
    assert e2["comprobante"] != e["comprobante"]                 # la extensión es otro cobro
    assert e2["importe"] == pytest.approx(z["tarifa_hora"] * 1.5)
    with SessionLocal() as db:                    # se adelanta el reloj: faltan 5 minutos
        fila = db.get(Estacionamiento, e["id"])
        fila.fin = datetime.now() + timedelta(minutes=5)
        db.commit()
        assert avisar_vencimientos_estacionamiento(db) == 1
        assert avisar_vencimientos_estacionamiento(db) == 0   # no repite el aviso
    assert any(n["tipo"] == "estacionamiento" for n in c.get("/api/notificaciones", headers=ana).json())


# ─── Tiempo real ─────────────────────────────────────────────────────────────
def test_eventos_exigen_sesion(c):
    assert c.get("/api/eventos").status_code == 422              # sin token
    assert c.get("/api/eventos", params={"token": "x"}).status_code == 401


def test_aviso_personal_solo_le_llega_a_su_dueno():
    import asyncio
    import json
    from app import eventos
    ana_q, juan_q = asyncio.Queue(), asyncio.Queue()
    eventos._clientes.update({ana_q: 1, juan_q: 2})
    try:
        eventos._repartir(json.dumps({"tipo": "notificacion", "datos": {"usuario_id": 1, "titulo": "Tu reclamo"}}))
        eventos._repartir(json.dumps({"tipo": "notificacion", "datos": {"usuario_id": None, "titulo": "Corte"}}))
        eventos._repartir(json.dumps({"tipo": "alarma", "datos": {"id": 3}}))
        assert ana_q.qsize() == 3                               # lo suyo y lo público
        assert juan_q.qsize() == 2                              # sólo lo público
        assert all("Tu reclamo" not in juan_q.get_nowait() for _ in range(2))
    finally:
        eventos._clientes.pop(ana_q), eventos._clientes.pop(juan_q)


# ─── 7. Notificaciones ───────────────────────────────────────────────────────
def test_aviso_municipal_y_preferencias(c, autoridad):
    juan = h(c, "31222333", "vecino123")
    c.put("/api/notificaciones/preferencias", headers=juan,
          json={"tipos": ["corte"], "barrios": ["Norte"], "frecuencia": "inmediata"})
    c.post("/api/notificaciones/enviar", headers=autoridad,
           json={"tipo": "obra", "titulo": "Obra en el Sur", "cuerpo": "Repavimentación", "barrio": "Sur"})
    c.post("/api/notificaciones/enviar", headers=autoridad,
           json={"tipo": "emergencia", "titulo": "Alerta meteorológica", "cuerpo": "Tormenta fuerte"})
    titulos = [n["titulo"] for n in c.get("/api/notificaciones", headers=juan).json()]
    assert "Obra en el Sur" not in titulos           # no es su tipo ni su zona
    assert "Alerta meteorológica" in titulos          # las emergencias llegan siempre
    assert c.put("/api/notificaciones/preferencias", headers=juan,
                 json={"tipos": ["inventado"], "barrios": []}).status_code == 422


def test_suscripcion_push(c, ana):
    assert len(c.get("/api/push/clave-publica").json()["clave"]) > 80
    r = c.post("/api/push/suscribir", headers=ana,
               json={"endpoint": "https://push.invalid/abc", "keys": {"p256dh": "x", "auth": "y"}})
    assert r.json()["ok"]


# ─── Residuos ────────────────────────────────────────────────────────────────
def test_vecino_registra_y_solicita(c, ana):
    assert c.post("/api/residuos/registros", headers=ana,
                  json={"categoria": "reciclable", "cantidad": 3, "unidad": "kg"}).status_code == 201
    assert c.get("/api/residuos/registros", headers=ana).json()["ultimos_30_dias"]["reciclable (kg)"] == 3
    s = c.post("/api/residuos/solicitudes", headers=ana,
               json={"tipo": "voluminoso", "descripcion": "Colchón de dos plazas", "direccion": "Casa 1",
                     "lat": -31.4250, "lng": -62.0800})
    assert s.status_code == 201
    fuera = c.post("/api/residuos/solicitudes", headers=ana,
                   json={"tipo": "voluminoso", "descripcion": "Fuera del ejido", "direccion": "Lejos",
                         "lat": -34.6, "lng": -58.4})
    assert fuera.status_code == 422
    assert len(c.get("/api/residuos/puntos-reciclaje").json()) == 5
    assert len(c.get("/api/residuos/horarios").json()) == 5


def test_ruta_planificada_escaneo_e_incidente(c, ana, autoridad, rec1):
    recs = c.get("/api/residuos/recolectores", headers=autoridad).json()
    r = c.post("/api/residuos/rutas", headers=autoridad,
               json={"recolector_id": recs[0]["id"], "umbral_llenado": 60})
    assert r.status_code == 201, r.text
    ruta = r.json()
    assert ruta["trazado"] == "recto"                      # OSRM apagado en las pruebas
    assert any(p["tipo"] == "solicitud" for p in ruta["paradas"])
    # Otra ruta no repite las paradas ya asignadas.
    r2 = c.post("/api/residuos/rutas", headers=autoridad,
                json={"recolector_id": recs[1]["id"], "umbral_llenado": 60})
    if r2.status_code == 201:
        ya = {(p["tipo"], p["id"]) for p in ruta["paradas"]}
        assert not ya & {(p["tipo"], p["id"]) for p in r2.json()["paradas"]}

    mia = c.get("/api/residuos/mi-ruta", headers=rec1).json()
    primera = mia["paradas"][0]["codigo"]
    assert c.post("/api/residuos/recolecciones", headers=rec1, json={"codigo": "SF-C-999"}).status_code == 404
    hecho = c.post("/api/residuos/recolecciones", headers=rec1, json={"codigo": primera.lower()})
    assert hecho.status_code == 201 and hecho.json()["hechas"] == 1
    assert c.post("/api/residuos/recolecciones", headers=rec1, json={"codigo": primera}).status_code == 409
    if primera.startswith("SF-C"):
        assert c.get(f"/api/residuos/contenedores/{primera}", headers=rec1).json()["llenado"] == 0

    for p in mia["paradas"][1:]:
        c.post("/api/residuos/recolecciones", headers=rec1, json={"codigo": p["codigo"]})
    assert c.get("/api/residuos/mi-ruta", headers=rec1).json() is None    # completada
    assert any(n["titulo"] == "Retiramos tu residuo especial"
               for n in c.get("/api/notificaciones", headers=ana).json())

    inc = c.post("/api/residuos/incidentes", headers=rec1,
                 json={"tipo": "contenedor_danado", "descripcion": "Tapa rota", "codigo": "SF-C-001"}).json()
    mapa = c.get("/api/residuos/mapa", headers=autoridad).json()
    assert any(i["id"] == inc["id"] for i in mapa["incidentes"])
    assert next(x for x in mapa["contenedores"] if x["codigo"] == "SF-C-001")["estado"] == "danado"
    c.patch(f"/api/residuos/incidentes/{inc['id']}", headers=autoridad)
    est = c.get("/api/residuos/estadisticas", headers=autoridad).json()
    assert est["recolecciones_hoy"] >= len(mia["paradas"])


# ─── Optimizador ─────────────────────────────────────────────────────────────
def test_dos_opt_nunca_empeora_y_visita_todo():
    rnd = random.Random(7)
    for _ in range(20):
        pts = [(-31.43 + rnd.uniform(-0.02, 0.02), -62.08 + rnd.uniform(-0.02, 0.02)) for _ in range(25)]
        nn = rutas.vecino_mas_cercano(pts)
        orden, km = rutas.optimizar(pts)
        largo_nn = rutas.largo([rutas.BASE] + [pts[k] for k in nn] + [rutas.BASE])
        assert sorted(orden) == list(range(25))
        assert km <= round(largo_nn, 2) + 1e-6


# ─── Push web de punta a punta (sin navegador) ──────────────────────────────
def test_push_cifrado_y_firmado_llega_al_servicio(c, autoridad, monkeypatch):
    """Un servicio de push falso recibe lo que manda el servidor: se comprueba la firma VAPID
    en el encabezado y que el contenido, cifrado según RFC 8291, se descifra con las claves
    del 'navegador' suscripto."""
    import base64
    import json as _json

    import http_ece
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from app import notificar as nt

    def b64(b):
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    clave_nav = ec.generate_private_key(ec.SECP256R1())
    publica = clave_nav.public_key().public_bytes(serialization.Encoding.X962,
                                                   serialization.PublicFormat.UncompressedPoint)
    secreto = b"0123456789abcdef"
    recibidos = []

    class Resp:
        status_code = 201
        text = ""

    def falso_post(url, data=None, headers=None, timeout=None, **kw):
        recibidos.append((url, data, headers))
        return Resp()

    monkeypatch.setattr("requests.post", falso_post)
    juan = h(c, "31222333", "vecino123")
    c.put("/api/notificaciones/preferencias", headers=juan,
          json={"tipos": ["evento"], "barrios": [], "frecuencia": "inmediata"})
    c.post("/api/push/suscribir", headers=juan,
           json={"endpoint": "https://push.example/sub/juan", "keys": {"p256dh": b64(publica), "auth": b64(secreto)}})
    c.post("/api/notificaciones/enviar", headers=autoridad,
           json={"tipo": "evento", "titulo": "Feria del libro", "cuerpo": "Sábado en la plaza"})

    url, cuerpo, enc = next(r for r in recibidos if r[0] == "https://push.example/sub/juan")
    assert enc["Authorization"].startswith("vapid t=") and nt.VAPID_PUBLIC in enc["Authorization"]
    plano = http_ece.decrypt(cuerpo, private_key=clave_nav, auth_secret=secreto, version="aes128gcm")
    assert _json.loads(plano)["titulo"] == "Feria del libro"
