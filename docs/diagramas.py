"""Genera los diagramas de los informes: arquitectura.svg (Geo Maps), arquitectura-tp5.svg y
flujo-residuos.svg.   Uso: python docs/diagramas.py
Mismos helpers que los diagramas de los TP anteriores: cada capa es una fila de cajas."""
from pathlib import Path
from xml.sax.saxutils import escape

FUENTE = "Segoe UI, Arial, sans-serif"
AZUL, VERDE, NARANJA, VIOLETA, ROJO, GRIS = "#3b6fb6", "#2e8b57", "#c47a1e", "#7a4fb0", "#b03a3a", "#555"


class Lienzo:
    def __init__(self, w, h):
        self.w, self.h, self.out = w, h, []

    def texto(self, x, y, s, tam=15, peso="normal", color="#1b1b1b", ancla="middle"):
        self.out.append(f'<text x="{x}" y="{y}" font-size="{tam}" font-weight="{peso}" fill="{color}" '
                        f'text-anchor="{ancla}">{escape(s)}</text>')

    def caja(self, x, y, w, h, titulo, sub="", borde=GRIS, fondo="#fff"):
        self.out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fondo}" '
                        f'stroke="{borde}" stroke-width="1.5"/>')
        lt, ls = titulo.split("\n"), (sub.split("\n") if sub else [])
        yy = y + (h - (18 * len(lt) + 15 * len(ls))) / 2 + 14
        for t in lt:
            self.texto(x + w / 2, yy, t, 14.5, "600")
            yy += 18
        for s in ls:
            self.texto(x + w / 2, yy, s, 12, color="#555")
            yy += 15

    def fila(self, y, h, cajas, borde, x0, x1, sep=10):
        ancho = (x1 - x0 - sep * (len(cajas) - 1)) / len(cajas)
        pos = []
        for i, (t, s) in enumerate(cajas):
            x = x0 + i * (ancho + sep)
            self.caja(x, y, ancho, h, t, s, borde)
            pos.append(x + ancho / 2)
        return pos

    def capa(self, x, y, w, h, nombre, fondo, borde, guiones=False):
        extra = ' stroke-dasharray="7 5"' if guiones else ""
        self.out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fondo}" '
                        f'stroke="{borde}" stroke-width="2"{extra}/>')
        self.texto(x + 14, y + 24, nombre, 15, "700", borde, "start")

    def flecha(self, x0, y0, x1, y1, etiqueta="", color="#444", doble=False, punteada=False, dx=8, dy=-5, ancla="start"):
        extra = ' stroke-dasharray="6 4"' if punteada else ""
        ini = ' marker-start="url(#flecha)"' if doble else ""
        self.out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{color}" stroke-width="2"{extra}'
                        f'{ini} marker-end="url(#flecha)"/>')
        if etiqueta:
            self.texto((x0 + x1) / 2 + dx, (y0 + y1) / 2 + dy, etiqueta, 12, "600", color, ancla)

    def guardar(self, ruta):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" font-family="{FUENTE}">'
               '<defs><marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
               'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#444"/></marker></defs>'
               f'<rect width="100%" height="100%" fill="#fff"/>{"".join(self.out)}</svg>')
        Path(ruta).write_text(svg, encoding="utf-8")
        print(ruta)


AQUI = Path(__file__).resolve().parent

# ─── Arquitectura completa (Geo Maps) ─────────────────────────────────────────
c = Lienzo(1100, 900)
c.capa(8, 8, 1084, 150, "CLIENTES · una app web progresiva (Ionic + React), empaquetable con Capacitor", "#eaf6ef", VERDE)
xs = c.fila(48, 96, [("App ciudadana", "registro de residuos, retiros\nespeciales, puntos, avisos"),
                     ("Panel de autoridades", "mapa en tiempo real, rutas,\nincidentes, campañas, QR"),
                     ("App de recolección", "ruta asignada, escaneo QR\ncon la cámara, incidentes")], VERDE, 20, 1080)

c.capa(8, 196, 1084, 92, "BORDE", "#eef3fa", AZUL)
c.caja(140, 226, 360, 52, "Ingress HTTPS", "cert-manager + Let's Encrypt", AZUL)
c.caja(600, 226, 360, 52, "web (nginx) × 2", "estáticos + balanceo de /api + SSE", AZUL)
for x in xs:
    c.flecha(x, 146, x if x < 500 else min(x, 960), 224, "", doble=True)
c.texto(730, 186, "HTTPS · token JWT · eventos SSE", 12.5, "600", "#333")
c.flecha(500, 252, 598, 252)

c.capa(8, 324, 1084, 330, "CLÚSTER KUBERNETES · namespace vecino-sf", "#f6f1fb", VIOLETA)
c.caja(30, 362, 380, 120, "api × 3 a 20 réplicas", "FastAPI · sin estado · /salud · /metrics\nreadiness y liveness probes\nPodDisruptionBudget: mínimo 2", VIOLETA)
c.caja(460, 362, 230, 120, "HorizontalPodAutoscaler", "objetivo 60 % de CPU\nsube +100 % cada 30 s\nbaja 1 pod por minuto", VIOLETA)
c.caja(720, 362, 350, 120, "simulador × 1", "sensores de llenado y bicicletas\navisos programados (vencimientos)\nen producción: IoT / CronJob", VIOLETA)
c.caja(30, 520, 300, 110, "PostgreSQL", "StatefulSet + volumen persistente\n(en la nube: servicio administrado)", VIOLETA)
c.caja(360, 520, 300, 110, "Redis pub/sub", "reparte los eventos en tiempo real\nentre todas las réplicas", VIOLETA)
c.caja(690, 520, 180, 110, "metrics-server", "CPU por pod\npara el HPA", VIOLETA)
c.caja(890, 520, 180, 110, "Prometheus", "lee /metrics de cada\npod de api (anotación)", VIOLETA)
c.flecha(780, 278, 300, 360, "/api", dx=-40, dy=-8)
c.flecha(180, 482, 180, 518, "SQL", doble=True)
c.flecha(380, 482, 470, 518, "publica / escucha", doble=True, dx=10)
c.flecha(800, 482, 650, 518, "publica", dx=-10, ancla="end")
c.flecha(760, 518, 620, 484, "CPU", punteada=True, dx=-30, dy=22)
c.flecha(458, 422, 412, 422, "")
c.texto(435, 412, "escala", 11.5, "600", "#444")

c.capa(8, 690, 530, 200, "SERVICIOS EXTERNOS", "#fdf3e6", NARANJA)
c.fila(726, 70, [("OpenStreetMap", "teselas del mapa"), ("OSRM", "trazado por calles")], NARANJA, 20, 526)
c.fila(806, 70, [("Push del navegador", "FCM · Mozilla · Apple\nfirmado con VAPID"), ("Google Maps", "navegación del\nrecolector")], NARANJA, 20, 526)
c.capa(562, 690, 530, 200, "MONITOREO", "#fbeeee", ROJO)
c.caja(580, 726, 230, 150, "Grafana", "pedidos/s por réplica\nlatencia p95\nerrores 5xx\nréplicas y conexiones", ROJO)
c.caja(840, 726, 230, 150, "Alertas (propuesta)", "p95 > 1 s durante 5 min\nerrores 5xx > 1 %\nréplicas = máximo", ROJO)
c.flecha(980, 630, 700, 724, "consulta", punteada=True, dx=-60)
c.flecha(250, 654, 250, 688, "OSRM · push", dx=10)
c.guardar(AQUI / "arquitectura.svg")

# ─── Arquitectura de la app no nativa (TP5) ──────────────────────────────────
c = Lienzo(1000, 700)
c.capa(8, 8, 984, 300, "APP WEB PROGRESIVA · Ionic 8 + React 18 + TypeScript (Vite)", "#eaf6ef", VERDE)
c.fila(48, 70, [("Bicicletas", "mapa + cercanía"), ("Tributaria", "cedulones y pagos"), ("Reclamos", "fotos + seguimiento"),
                ("Líneas", "llamar · mail · WhatsApp")], VERDE, 24, 976)
c.fila(126, 70, [("Alarmas", "estado en vivo + zonas"), ("Estacionamiento", "pago + temporizador"),
                 ("Notificaciones", "historial + preferencias"), ("Residuos", "caso Geo Maps")], VERDE, 24, 976)
c.fila(214, 76, [("Componentes Ionic", "UI móvil, gestos, navegación"), ("Leaflet + OSM", "mapas sin clave"),
                 ("Service worker", "instalable, sin conexión, push"), ("Capacitor", "mismo código como app\nAndroid / iOS")], GRIS, 24, 976)
c.flecha(500, 308, 500, 368, "HTTPS (fetch + JSON) · token JWT · SSE para el tiempo real", doble=True, dx=12)
c.capa(8, 372, 984, 150, "API REST · FastAPI (Python)", "#f6f1fb", VIOLETA)
c.fila(410, 96, [("Sesión y roles", "JWT · vecino / autoridad /\nrecolector"), ("Servicios municipales", "7 módulos con\nAPIs simuladas"),
                 ("Notificaciones", "historial · preferencias\nWeb Push (VAPID)"), ("Tiempo real", "Server-Sent Events\n+ Redis entre réplicas")], VIOLETA, 24, 976)
c.flecha(500, 522, 500, 572, "", doble=True)
c.capa(8, 576, 984, 116, "DATOS E INTEGRACIONES", "#fdf3e6", NARANJA)
c.fila(612, 66, [("PostgreSQL", "SQLite en desarrollo"), ("Pasarela de pagos", "simulada"), ("Sistemas del municipio", "simulados con la forma\nde su API"),
                 ("Servicios de push", "del navegador")], NARANJA, 24, 976)
c.guardar(AQUI / "arquitectura-tp5.svg")

# ─── Flujo de trabajo de la recolección ─────────────────────────────────────
c = Lienzo(1000, 470)
carriles = [("Vecino", VERDE), ("Autoridad", AZUL), ("Sistema", VIOLETA), ("Recolector", NARANJA)]
for i, (n, col) in enumerate(carriles):
    y = 10 + i * 112
    c.capa(8, y, 984, 104, n.upper(), "#fafafa", col)
pasos = [
    (0, 120, "Pide retiro\nespecial", "foto del mapa"), (2, 120, "Sensor informa\nllenado", "contenedores"),
    (1, 300, "Planifica", "umbral %, zonas,\nrecolector"), (2, 470, "Optimiza", "vecino más cercano\n+ 2-opt · OSRM"),
    (3, 640, "Recibe la ruta", "push + mapa\nen orden"), (3, 810, "Escanea QR", "o tipea el código"),
    (2, 810, "Registra", "llenado 0 %\nSSE al panel"), (0, 810, "Aviso: «retiramos\ntu residuo»", "push"),
    (1, 640, "Ve el avance", "en tiempo real"),
]
pos = {}
for k, (carril, x, t, s) in enumerate(pasos):
    y = 10 + carril * 112 + 34
    c.caja(x - 75, y, 150, 62, t, s, carriles[carril][1])
    pos[k] = (x, y)
for a, b in [(0, 2), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (6, 8)]:
    (x0, y0), (x1, y1) = pos[a], pos[b]
    if y0 == y1:
        c.flecha(x0 + 75, y0 + 31, x1 - 77, y1 + 31)
    else:
        c.flecha(x0 + (0 if x0 == x1 else 75), y0 + (62 if y1 > y0 else 0), x1 - (0 if x0 == x1 else 75), y1 + (0 if y1 > y0 else 62))
c.guardar(AQUI / "flujo-residuos.svg")
