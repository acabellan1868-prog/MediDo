"""
MediDo — Ruta /api/contenedores.
Lista de contenedores Docker con su estado.
"""

from fastapi import APIRouter

from app.recolector_docker import listar_contenedores

ruta = APIRouter()


@ruta.get("")
def lista():
    """Devuelve la lista de contenedores Docker con estado y uptime."""
    contenedores = listar_contenedores()
    total = len(contenedores)
    running = sum(1 for c in contenedores if c["estado"] == "running")

    return {
        "total": total,
        "running": running,
        "stopped": total - running,
        "contenedores": contenedores,
    }
