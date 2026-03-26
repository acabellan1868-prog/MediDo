"""
MediDo — Logica de alertas y notificaciones NTFY.
Evalua umbrales de metricas y envia notificaciones proactivas.
"""

import logging
import httpx

from app.config import NTFY_URL, NTFY_TOPIC, CONTENEDORES_IGNORADOS, DIAS_RETENCION

logger = logging.getLogger("medido.alertador")

# Umbrales de alerta
UMBRALES = {
    "cpu": {"warning": 80, "danger": 95},
    "ram": {"warning": 85, "danger": 95},
    "disco": {"warning": 80, "danger": 90},
}


def enviar_ntfy(titulo: str, cuerpo: str, prioridad: str = "default") -> bool:
    """Envia una notificacion via NTFY."""
    url = f"{NTFY_URL}/{NTFY_TOPIC}"
    tags = "warning,desktop_computer"
    if prioridad == "high":
        tags = "rotating_light,desktop_computer"

    try:
        respuesta = httpx.post(
            url,
            content=cuerpo.encode("utf-8"),
            headers={
                "Title": titulo,
                "Priority": prioridad,
                "Tags": tags,
            },
            timeout=10.0,
        )
        respuesta.raise_for_status()
        logger.info(f"NTFY enviado: {titulo}")
        return True
    except Exception as e:
        logger.error(f"Error enviando NTFY: {e}")
        return False


def _crear_alerta(tipo: str, mensaje: str, servicio: str = None, notificar: bool = False):
    """Crea una alerta en BD y opcionalmente la envia por NTFY."""
    from app import bd

    # No duplicar alertas activas del mismo tipo y servicio
    existente = bd.consultar_uno(
        """SELECT id FROM alertas
           WHERE tipo = ? AND servicio IS ? AND resuelta = 0
           AND fecha > datetime('now', '-1 hour')""",
        (tipo, servicio),
    )
    if existente:
        return

    bd.ejecutar(
        "INSERT INTO alertas (tipo, mensaje, servicio, enviada) VALUES (?, ?, ?, ?)",
        (tipo, mensaje, servicio, 1 if notificar else 0),
    )

    if notificar:
        titulo = f"MediDo: {tipo}"
        enviar_ntfy(titulo, mensaje, "high" if "danger" in tipo else "default")


def evaluar_metricas(datos_proxmox: dict):
    """
    Evalua las metricas de Proxmox contra los umbrales.
    Crea alertas si se superan.
    """
    host = datos_proxmox.get("host")
    if not host:
        return

    # CPU del host
    cpu = host["cpu_percent"]
    if cpu > UMBRALES["cpu"]["danger"]:
        _crear_alerta(
            "cpu_danger",
            f"CPU del host al {cpu}% (umbral: {UMBRALES['cpu']['danger']}%)",
            "proxmox-host",
            notificar=True,
        )
    elif cpu > UMBRALES["cpu"]["warning"]:
        _crear_alerta(
            "cpu_warning",
            f"CPU del host al {cpu}% (umbral: {UMBRALES['cpu']['warning']}%)",
            "proxmox-host",
        )

    # RAM del host
    ram = host["memoria"]["percent"]
    if ram > UMBRALES["ram"]["danger"]:
        _crear_alerta(
            "ram_danger",
            f"RAM del host al {ram}% (umbral: {UMBRALES['ram']['danger']}%)",
            "proxmox-host",
            notificar=True,
        )
    elif ram > UMBRALES["ram"]["warning"]:
        _crear_alerta(
            "ram_warning",
            f"RAM del host al {ram}% (umbral: {UMBRALES['ram']['warning']}%)",
            "proxmox-host",
        )

    # Disco de cada VM
    for vm in datos_proxmox.get("vms", []):
        if vm["estado"] != "running":
            continue
        disco = vm["disco"]["percent"]
        nombre = vm["nombre"]
        if disco > UMBRALES["disco"]["danger"]:
            _crear_alerta(
                "disco_danger",
                f"Disco de {nombre} al {disco}% (umbral: {UMBRALES['disco']['danger']}%)",
                f"vm-{vm['vmid']}",
                notificar=True,
            )
        elif disco > UMBRALES["disco"]["warning"]:
            _crear_alerta(
                "disco_warning",
                f"Disco de {nombre} al {disco}% (umbral: {UMBRALES['disco']['warning']}%)",
                f"vm-{vm['vmid']}",
            )


def evaluar_contenedores(contenedores: list[dict]):
    """
    Detecta contenedores parados que no esten en la lista de ignorados.
    """
    for c in contenedores:
        if c["estado"] != "running" and c["nombre"] not in CONTENEDORES_IGNORADOS:
            _crear_alerta(
                "contenedor_parado",
                f"Contenedor '{c['nombre']}' esta parado",
                c["nombre"],
                notificar=True,
            )


def evaluar_servicios(resultados: list[dict]):
    """
    Evalua resultados de health checks.
    Alerta si un servicio lleva 3+ checks consecutivos caido.
    """
    from app import bd

    for r in resultados:
        if r["estado"] in ("caido", "error"):
            # Contar checks consecutivos fallidos
            ultimos = bd.consultar_todos(
                """SELECT estado FROM health_checks
                   WHERE servicio = ?
                   ORDER BY fecha DESC LIMIT 3""",
                (r["servicio"],),
            )
            fallidos = sum(
                1 for u in ultimos if u["estado"] in ("caido", "error")
            )
            if fallidos >= 3:
                _crear_alerta(
                    "servicio_caido",
                    f"Servicio '{r['servicio']}' caido ({fallidos} checks consecutivos)",
                    r["servicio"],
                    notificar=True,
                )


def limpiar_historial():
    """Elimina registros antiguos (mas de DIAS_RETENCION dias)."""
    from app import bd

    umbral = f"-{DIAS_RETENCION} days"

    borrados_metricas = bd.ejecutar(
        "DELETE FROM metricas WHERE fecha < datetime('now', ?)", (umbral,)
    )
    borrados_health = bd.ejecutar(
        "DELETE FROM health_checks WHERE fecha < datetime('now', ?)", (umbral,)
    )
    borrados_alertas = bd.ejecutar(
        "DELETE FROM alertas WHERE fecha < datetime('now', ?) AND resuelta = 1",
        (umbral,),
    )

    logger.info(
        f"Limpieza: metricas={borrados_metricas}, "
        f"health={borrados_health}, alertas={borrados_alertas}"
    )
