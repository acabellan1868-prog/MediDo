"""
MediDo — Rutas /api/proxmox.
Metricas actuales e historial del servidor Proxmox.
"""

from fastapi import APIRouter, Query

from app import bd
from app.recolector_proxmox import recolectar_proxmox

ruta = APIRouter()


@ruta.get("")
def estado_actual():
    """Devuelve metricas actuales de Proxmox (host + VMs + almacenamiento)."""
    return recolectar_proxmox()


@ruta.get("/historial")
def historial(horas: int = Query(24, ge=1, le=168)):
    """Devuelve serie temporal de metricas del sistema."""
    filas = bd.consultar_todos(
        """SELECT fecha,
                  pve_cpu_percent, pve_memoria_percent,
                  vm_cpu_percent, vm_memoria_percent, vm_disco_percent,
                  contenedores_running, contenedores_total
           FROM metricas
           WHERE fecha > datetime('now', ? || ' hours')
           ORDER BY fecha ASC""",
        (f"-{horas}",),
    )
    return {"horas": horas, "puntos": filas}
