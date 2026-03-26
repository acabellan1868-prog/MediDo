"""
MediDo — Configuracion centralizada.
Lee variables de entorno con valores por defecto para desarrollo local.
"""

import os

# Base de datos
RUTA_BD = os.environ.get("MEDIDO_DB_PATH", "data/medido.db")

# Proxmox API
PVE_HOST = os.environ.get("PVE_HOST", "192.168.31.103")
PVE_NODE = os.environ.get("PVE_NODE", "deeloco")
PVE_TOKEN_ID = os.environ.get("PVE_TOKEN_ID", "root@pam!medido")
PVE_TOKEN_SECRET = os.environ.get("PVE_TOKEN_SECRET", "")
PVE_VERIFY_SSL = os.environ.get("PVE_VERIFY_SSL", "false").lower() == "true"

# Notificaciones NTFY
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "hogaros-3ca6f61b")

# Intervalos de recoleccion (segundos)
INTERVALO_HEALTH = int(os.environ.get("MEDIDO_INTERVALO_HEALTH", "60"))
INTERVALO_METRICAS = int(os.environ.get("MEDIDO_INTERVALO_METRICAS", "300"))

# Retencion de historial (dias)
DIAS_RETENCION = int(os.environ.get("MEDIDO_DIAS_RETENCION", "90"))

# Home Assistant (para health check)
HA_TOKEN = os.environ.get("HA_TOKEN", "")

# Contenedores a ignorar en alertas (separados por coma)
CONTENEDORES_IGNORADOS = [
    c.strip()
    for c in os.environ.get("MEDIDO_CONTENEDORES_IGNORADOS", "").split(",")
    if c.strip()
]

# Zona horaria
TZ = os.environ.get("TZ", "Europe/Madrid")
