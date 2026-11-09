# Vecino SF

Aplicación web progresiva de servicios municipales para San Francisco (Córdoba), con el sistema
de gestión de residuos vecinales. Trabajos de **Arquitecturas Móviles 2026** (UTN FRSFCO):

- **Práctico 5 — Estrategias de arquitecturas móviles no nativas:** bicicletas públicas, tributaria,
  reclamos, líneas de atención, alarmas comunitarias, estacionamiento medido y notificaciones.
- **Caso Gestión de Residuos (Geo Maps):** app ciudadana, panel de autoridades, app de recolección,
  mapas y rutas optimizadas, push, Docker, Kubernetes con autoescalado y monitoreo.

> Prototipo con **datos simulados**: estaciones, contenedores, alarmas, montos y contactos no son
> datos reales del municipio. Las integraciones que no tienen API pública (tributaria, pagos,
> sensores) están simuladas con la forma que tendría su API.

## Estructura

| Carpeta | Qué hay |
|---|---|
| `backend/` | API en FastAPI (Python): `app/routers/` servicios agrupados por área, `app/rutas.py` optimizador, `app/eventos.py` tiempo real, `app/notificar.py` push |
| `frontend/` | App en Ionic 8 + React 18 + TypeScript (Vite), PWA y Capacitor |
| `deploy/` | `docker-compose.yml`, `k8s/` (manifiestos), Prometheus, Grafana y pruebas de carga |
| `docs/` | Informes, diagramas, capturas y registros de las pruebas |

## Correr en desarrollo

```bash
cd backend && pip install -r requirements.txt pytest
SIMULADOR_INTERNO=1 uvicorn app.main:app --port 8000        # SQLite, sin Redis
cd frontend && npm ci && npm run dev                          # http://localhost:5173
```

Usuarios de prueba: vecino `30111222` / `vecino123`, autoridad `autoridad` / `autoridad123`,
recolector `recolector1` / `recolector123` (botones en la pantalla de ingreso).

## Pruebas

```bash
cd backend && python -m pytest -q                 # 21 pruebas de la API
cd frontend && npx vite build && npx vite preview  # y con el backend arriba:
node pruebas/capturas.mjs                          # recorrido completo de las 3 apps + capturas
```

## Docker y Kubernetes

```bash
cd deploy && docker compose up -d --build          # app :8080 · Grafana :3000 · Prometheus :9090
docker compose up -d --scale api=6                 # escalar el backend
bash carga_paralela.sh 3 3 40                      # prueba de carga (3 réplicas, 120 usuarios)
bash bateria_carga.sh                              # 1, 3 y 6 réplicas + redundancia → docs/prueba-carga.log
# tiempo real entre réplicas (con 3 réplicas arriba) → docs/prueba-tiempo-real.log
docker run --rm --network vecino-sf_default -v "$PWD:/w:ro" vecino-carga python /w/prueba_tiempo_real.py
```

Kubernetes (probado en k3s):

```bash
kubectl apply -f deploy/k8s/00-base.yaml
kubectl -n vecino-sf create secret generic vecino-vapid \
  --from-literal=VAPID_PUBLIC=<clave pública> --from-literal=VAPID_PRIVATE=<clave privada>
kubectl apply -f deploy/k8s/
kubectl -n vecino-sf get hpa api -w
bash deploy/k8s/prueba/corrida.sh 3 20 docs/prueba-hpa.log   # prueba de autoescalado (clúster k3s de prueba)
```

Las claves VAPID se generan una vez (por ejemplo con `npx web-push generate-vapid-keys`).
