"""
MediDo — Rutas /api/servicios.
Estado actual e historial de health checks.
"""

from fastapi import APIRouter, Query

from app import bd

ruta = APIRouter()


@ruta.get("")
def estado_actual():
    """Devuelve el ultimo health check de cada servicio."""
    servicios = bd.consultar_todos(
        """SELECT servicio, estado, tiempo_respuesta_ms, codigo_http, mensaje, fecha
           FROM health_checks
           WHERE id IN (
               SELECT MAX(id) FROM health_checks GROUP BY servicio
           )
           ORDER BY servicio"""
    )
    return {"servicios": servicios}


@ruta.get("/{nombre}/historial")
def historial(nombre: str, horas: int = Query(24, ge=1, le=168)):
    """Devuelve historial de health checks de un servicio."""
    filas = bd.consultar_todos(
        """SELECT fecha, estado, tiempo_respuesta_ms, codigo_http, mensaje
           FROM health_checks
           WHERE servicio = ?
             AND fecha > datetime('now', ? || ' hours')
           ORDER BY fecha ASC""",
        (nombre, f"-{horas}"),
    )
    return {"servicio": nombre, "horas": horas, "puntos": filas}
