"""
MediDo — Recolector de estado de contenedores Docker.
Usa el SDK de Docker para listar contenedores y sus metricas.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("medido.docker")


def _obtener_cliente():
    """Crea un cliente Docker usando el socket montado."""
    import docker
    return docker.from_env()


def listar_contenedores() -> list[dict]:
    """
    Lista todos los contenedores Docker con su estado y metricas basicas.
    No recoge stats de CPU/memoria (tarda demasiado con muchos contenedores).
    """
    try:
        cliente = _obtener_cliente()
        contenedores_docker = cliente.containers.list(all=True)
    except Exception as e:
        logger.error(f"Error conectando con Docker: {e}")
        return []

    contenedores = []
    ahora = datetime.now(timezone.utc)

    for c in contenedores_docker:
        # Calcular uptime si esta running
        uptime_horas = None
        inicio = None
        if c.status == "running" and c.attrs.get("State", {}).get("StartedAt"):
            try:
                started = c.attrs["State"]["StartedAt"]
                # Docker devuelve ISO 8601, truncar nanosegundos
                if "." in started:
                    started = started[:started.index(".")] + "+00:00"
                dt_inicio = datetime.fromisoformat(started)
                inicio = dt_inicio.isoformat()
                delta = ahora - dt_inicio
                uptime_horas = round(delta.total_seconds() / 3600, 1)
            except Exception:
                pass

        # Salud del healthcheck (si lo tiene configurado)
        salud = None
        health = c.attrs.get("State", {}).get("Health")
        if health:
            salud = health.get("Status", "none")

        contenedores.append({
            "nombre": c.name,
            "imagen": c.image.tags[0] if c.image.tags else str(c.image.short_id),
            "estado": c.status,
            "salud": salud,
            "inicio": inicio,
            "uptime_horas": uptime_horas,
        })

    # Ordenar: running primero, luego por nombre
    contenedores.sort(key=lambda x: (0 if x["estado"] == "running" else 1, x["nombre"]))

    logger.info(
        f"Docker: {sum(1 for c in contenedores if c['estado'] == 'running')} running "
        f"/ {len(contenedores)} total"
    )

    return contenedores


def recolectar_docker() -> dict:
    """
    Recolecta estado de contenedores y devuelve resumen.
    Actualiza conteos en la ultima fila de metricas si existe.
    """
    from app import bd

    contenedores = listar_contenedores()
    total = len(contenedores)
    running = sum(1 for c in contenedores if c["estado"] == "running")
    stopped = total - running

    resumen = {
        "contenedores": contenedores,
        "total": total,
        "running": running,
        "stopped": stopped,
    }

    # Actualizar la ultima fila de metricas (la que creo recolector_proxmox)
    ultima = bd.consultar_uno(
        "SELECT id FROM metricas ORDER BY id DESC LIMIT 1"
    )
    if ultima:
        bd.ejecutar(
            """UPDATE metricas SET
                contenedores_total = ?,
                contenedores_running = ?,
                contenedores_stopped = ?
            WHERE id = ?""",
            (total, running, stopped, ultima["id"]),
        )

    return resumen
