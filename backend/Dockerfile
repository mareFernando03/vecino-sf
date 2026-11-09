FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Sin privilegios de root dentro del contenedor.
RUN useradd -m vecino && mkdir -p /datos/adjuntos /compartido && chown -R vecino /app /datos /compartido
USER vecino
ENV UPLOAD_DIR=/datos/adjuntos VAPID_FILE=/datos/vapid.json
EXPOSE 8000
# Un solo proceso por contenedor: se escala sumando réplicas (Kubernetes), no procesos. Así el
# pool de conexiones y las métricas de Prometheus son uno por réplica y las cuentas cierran.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
