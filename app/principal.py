"""
MediDo — Punto de entrada de la aplicacion FastAPI.
Inicializa la BD, configura recolectores periodicos y registra todas las rutas.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.bd import inicializar_bd, migrar_bd
from app.config import RUTA_BD, INTERVALO_HEALTH, INTERVALO_METRICAS
from app.recolector_proxmox import recolectar_proxmox
from app.recolector_docker import recolectar_docker
from app.health_checker import ejecutar_health_checks
from app.alertador import evaluar_metricas, evaluar_contenedores, evaluar_servicios, limpiar_historial
from app.rutas import resumen, proxmox, contenedores, servicios, alertas, claude

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("medido")

# Planificador de tareas periodicas
planificador = BackgroundScheduler()


def recolectar_todo():
    """Recolecta metricas de Proxmox + Docker y evalua alertas."""
    try:
        datos_proxmox = recolectar_proxmox()
        datos_docker = recolectar_docker()
        evaluar_metricas(datos_proxmox)
        evaluar_contenedores(datos_docker.get("contenedores", []))
    except Exception as e:
        logger.error(f"Error en recoleccion de metricas: {e}")


def ciclo_health():
    """Ejecuta health checks y evalua alertas de servicios."""
    try:
        resultados = ejecutar_health_checks()
        evaluar_servicios(resultados)
    except Exception as e:
        logger.error(f"Error en health checks: {e}")


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    """Se ejecuta al arrancar la app: crea BD y lanza recolectores periodicos."""
    # Asegurar que el directorio de datos existe
    directorio_bd = os.path.dirname(RUTA_BD)
    if directorio_bd:
        os.makedirs(directorio_bd, exist_ok=True)

    migrar_bd()
    inicializar_bd()

    # Recoleccion de metricas (Proxmox + Docker) cada INTERVALO_METRICAS
    planificador.add_job(
        recolectar_todo,
        "interval",
        seconds=INTERVALO_METRICAS,
        id="recoleccion_metricas",
        name="Recoleccion de metricas (Proxmox + Docker)",
        replace_existing=True,
    )

    # Health checks cada INTERVALO_HEALTH
    planificador.add_job(
        ciclo_health,
        "interval",
        seconds=INTERVALO_HEALTH,
        id="health_checks",
        name="Health checks de servicios",
        replace_existing=True,
    )

    # Limpieza nocturna de historial (cada dia a las 04:00)
    planificador.add_job(
        limpiar_historial,
        CronTrigger(hour=4, minute=0),
        id="limpieza_historial",
        name="Limpieza nocturna de historial",
        replace_existing=True,
    )

    planificador.start()
    logger.info(f"Metricas cada {INTERVALO_METRICAS}s, health checks cada {INTERVALO_HEALTH}s")

    # Ejecutar primera recoleccion al arrancar
    logger.info("Ejecutando recoleccion inicial...")
    recolectar_todo()
    ciclo_health()

    yield

    # Apagar planificador al cerrar
    planificador.shutdown(wait=False)
    logger.info("Planificador detenido")


app = FastAPI(
    title="MediDo — Metricas del Hogar",
    description="Monitorizacion de salud del ecosistema hogarOS",
    version="1.0.0",
    lifespan=ciclo_vida,
)

# ---- Registrar rutas API ----
app.include_router(resumen.ruta, prefix="/api/resumen", tags=["Resumen"])
app.include_router(proxmox.ruta, prefix="/api/proxmox", tags=["Proxmox"])
app.include_router(contenedores.ruta, prefix="/api/contenedores", tags=["Contenedores"])
app.include_router(servicios.ruta, prefix="/api/servicios", tags=["Servicios"])
app.include_router(alertas.ruta, prefix="/api/alertas", tags=["Alertas"])
app.include_router(claude.ruta, prefix="/api/claude", tags=["Claude Code"])

# ---- Servir frontend estatico (DEBE ir al final, es catch-all) ----
app.mount("/", StaticFiles(directory="static", html=True), name="static")
