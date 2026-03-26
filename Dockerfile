FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo y frontend
COPY app/ app/
COPY static/ static/

# Puerto de la aplicacion
ENV MEDIDO_PORT=8084
EXPOSE 8084

# Arrancar uvicorn
CMD uvicorn app.principal:app --host 0.0.0.0 --port $MEDIDO_PORT
