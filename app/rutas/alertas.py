"""
MediDo — Rutas /api/alertas.
Gestion de alertas activas y resolucion.
"""

from fastapi import APIRouter

from app import bd

ruta = APIRouter()


@ruta.get("")
def listar():
    """Devuelve alertas activas y las 50 mas recientes."""
    alertas = bd.consultar_todos(
        """SELECT id, tipo, mensaje, servicio, fecha, enviada, resuelta
           FROM alertas
           ORDER BY resuelta ASC, fecha DESC
           LIMIT 50"""
    )
    activas = sum(1 for a in alertas if not a["resuelta"])
    return {"activas": activas, "alertas": alertas}


@ruta.post("/{alerta_id}/resolver")
def resolver(alerta_id: int):
    """Marca una alerta como resuelta."""
    bd.ejecutar(
        "UPDATE alertas SET resuelta = 1 WHERE id = ?",
        (alerta_id,),
    )
    return {"ok": True, "id": alerta_id}
