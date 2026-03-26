"""
MediDo — Ruta /api/resumen.
Endpoint principal para la tarjeta del portal.
"""

from fastapi import APIRouter

from app import bd

ruta = APIRouter()


@ruta.get("")
def resumen():
    """Devuelve el estado general del sistema para la tarjeta del portal."""

    # Ultima metrica de Proxmox + Docker
    metrica = bd.consultar_uno(
        "SELECT * FROM metricas ORDER BY fecha DESC LIMIT 1"
    )

    # Ultimo health check de cada servicio
    servicios = bd.consultar_todos(
        """SELECT servicio, estado, tiempo_respuesta_ms
           FROM health_checks
           WHERE id IN (
               SELECT MAX(id) FROM health_checks GROUP BY servicio
           )"""
    )
    servicios_ok = sum(1 for s in servicios if s["estado"] == "ok")
    servicios_total = len(servicios)

    # Alertas activas (no resueltas)
    alertas = bd.consultar_uno(
        "SELECT COUNT(*) as total FROM alertas WHERE resuelta = 0"
    )
    alertas_activas = alertas["total"] if alertas else 0

    # Determinar estado global
    estado_global = "ok"
    if alertas_activas > 0 or (servicios_total > 0 and servicios_ok < servicios_total):
        estado_global = "warning"
    if metrica:
        if (metrica.get("pve_cpu_percent") or 0) > 95:
            estado_global = "danger"
        if (metrica.get("pve_memoria_percent") or 0) > 95:
            estado_global = "danger"
        if (metrica.get("vm_disco_percent") or 0) > 90:
            estado_global = "danger"

    # Construir respuesta
    resultado = {
        "estado_global": estado_global,
        "pve_cpu_percent": metrica["pve_cpu_percent"] if metrica else None,
        "pve_memoria_percent": metrica["pve_memoria_percent"] if metrica else None,
        "vm_cpu_percent": metrica["vm_cpu_percent"] if metrica else None,
        "vm_memoria_percent": metrica["vm_memoria_percent"] if metrica else None,
        "vm_disco_percent": metrica["vm_disco_percent"] if metrica else None,
        "contenedores_running": metrica["contenedores_running"] if metrica else None,
        "contenedores_total": metrica["contenedores_total"] if metrica else None,
        "servicios_ok": servicios_ok,
        "servicios_total": servicios_total,
        "alertas_activas": alertas_activas,
    }

    return resultado
