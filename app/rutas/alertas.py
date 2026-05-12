"""
MediDo — Rutas /api/alertas.
Gestion de alertas activas, resolucion, silenciado y eliminacion.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import bd

ruta = APIRouter()


class SilenciarCuerpo(BaseModel):
    """Cuerpo de la petición para silenciar una alerta."""
    horas: int | None = None
    permanente: bool = False


@ruta.get("")
def listar():
    """Devuelve alertas activas y las 50 mas recientes."""
    alertas = bd.consultar_todos(
        """SELECT id, tipo, mensaje, servicio, fecha, enviada, resuelta, silenciada_hasta
           FROM alertas
           ORDER BY resuelta ASC, fecha DESC
           LIMIT 50"""
    )
    activas = sum(
        1 for a in alertas
        if not a["resuelta"] and not _esta_silenciada(a["silenciada_hasta"])
    )
    return {"modulo": "medido", "activas": activas, "alertas": alertas}


def _esta_silenciada(silenciada_hasta: str | None) -> bool:
    """Devuelve True si la alerta está dentro del período de silencio."""
    if not silenciada_hasta:
        return False
    if silenciada_hasta == "9999-12-31":
        return True
    try:
        hasta = datetime.fromisoformat(silenciada_hasta)
        return datetime.now(timezone.utc) < hasta.replace(tzinfo=timezone.utc)
    except ValueError:
        return False


@ruta.post("/{alerta_id}/resolver")
def resolver(alerta_id: int):
    """Marca una alerta como resuelta."""
    bd.ejecutar(
        "UPDATE alertas SET resuelta = 1 WHERE id = ?",
        (alerta_id,),
    )
    return {"ok": True, "id": alerta_id}


@ruta.post("/{alerta_id}/silenciar")
def silenciar(alerta_id: int, cuerpo: SilenciarCuerpo):
    """Silencia una alerta temporalmente (horas) o de forma permanente."""
    existente = bd.consultar_uno(
        "SELECT id FROM alertas WHERE id = ?", (alerta_id,)
    )
    if not existente:
        raise HTTPException(404, "Alerta no encontrada")

    if cuerpo.permanente:
        hasta = "9999-12-31"
    elif cuerpo.horas and cuerpo.horas > 0:
        hasta = (datetime.now(timezone.utc) + timedelta(hours=cuerpo.horas)).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        raise HTTPException(400, "Indica horas o permanente=true")

    bd.ejecutar(
        "UPDATE alertas SET silenciada_hasta = ? WHERE id = ?", (hasta, alerta_id)
    )
    return {"ok": True, "id": alerta_id, "silenciada_hasta": hasta}


@ruta.post("/{alerta_id}/activar")
def activar(alerta_id: int):
    """Quita el silencio de una alerta (vuelve a ser activa)."""
    existente = bd.consultar_uno(
        "SELECT id FROM alertas WHERE id = ?", (alerta_id,)
    )
    if not existente:
        raise HTTPException(404, "Alerta no encontrada")

    bd.ejecutar(
        "UPDATE alertas SET silenciada_hasta = NULL WHERE id = ?", (alerta_id,)
    )
    return {"ok": True, "id": alerta_id}


@ruta.delete("/{alerta_id}")
def eliminar(alerta_id: int):
    """Elimina una alerta."""
    existente = bd.consultar_uno(
        "SELECT id FROM alertas WHERE id = ?", (alerta_id,)
    )
    if not existente:
        raise HTTPException(404, "Alerta no encontrada")

    bd.ejecutar("DELETE FROM alertas WHERE id = ?", (alerta_id,))
    return {"ok": True, "id": alerta_id}
