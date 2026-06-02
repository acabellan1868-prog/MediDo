"""
MediDo — Rutas /api/polar.
Exposición de datos deportivos sincronizados desde Polar Flow.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from app import bd
from app.polar_client import sincronizar_ejercicios, _obtener_datos_ruta
import httpx

logger = logging.getLogger("medido.polar")
ruta = APIRouter()


# ---- HELPERS ----

def _formatear_duracion(segundos: int) -> str:
    """Convierte segundos a string legible (1h 30m 15s)."""
    h = segundos // 3600
    m = (segundos % 3600) // 60
    s = segundos % 60
    partes = []
    if h:
        partes.append(f"{h}h")
    if m:
        partes.append(f"{m}m")
    if s and not h:  # Solo mostrar segundos si no hay horas
        partes.append(f"{s}s")
    return " ".join(partes) if partes else "0m"


# ---- ENDPOINTS ----

@ruta.get("/resumen")
def resumen_polar(dias: int = 7):
    """
    Resumen de actividad deportiva de los últimos N días.
    Devuelve: nº actividades, km totales, calorías, FC media, últimas actividades,
    desglose por tipo de deporte.
    """
    desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")

    # Totales del período
    totales = bd.consultar_uno(
        """
        SELECT
            COUNT(*) as num_actividades,
            COALESCE(SUM(distancia_km), 0) as km_totales,
            COALESCE(SUM(calorias), 0) as calorias_totales,
            COALESCE(SUM(duracion_segundos), 0) as duracion_total_segundos,
            COALESCE(AVG(CASE WHEN fc_promedio IS NOT NULL THEN fc_promedio END), 0) as fc_promedio_general
        FROM actividades_polar
        WHERE date(fecha_inicio) >= ?
        """,
        (desde,),
    )

    # Últimas actividades del período
    ultimas = bd.consultar_todos(
        """
        SELECT polar_id, fecha_inicio, tipo, distancia_km,
               duracion_segundos, calorias, fc_promedio, fc_maxima,
               velocidad_media_kmh, velocidad_maxima_kmh,
               desnivel_positivo, desnivel_negativo, tiene_ruta
        FROM actividades_polar
        WHERE date(fecha_inicio) >= ?
        ORDER BY fecha_inicio DESC
        LIMIT 10
        """,
        (desde,),
    )

    # Desglose por tipo de deporte
    por_tipo = bd.consultar_todos(
        """
        SELECT tipo,
               COUNT(*) as count,
               COALESCE(SUM(distancia_km), 0) as km,
               COALESCE(SUM(calorias), 0) as calorias,
               COALESCE(SUM(duracion_segundos), 0) as duracion_segundos
        FROM actividades_polar
        WHERE date(fecha_inicio) >= ?
        GROUP BY tipo
        ORDER BY count DESC
        """,
        (desde,),
    )

    return {
        "periodo_dias": dias,
        "desde": desde,
        "num_actividades": totales["num_actividades"] if totales else 0,
        "km_totales": round(totales["km_totales"], 2) if totales else 0,
        "calorias_totales": int(totales["calorias_totales"]) if totales else 0,
        "duracion_total_minutos": int((totales["duracion_total_segundos"] or 0) / 60) if totales else 0,
        "fc_promedio_general": int(totales["fc_promedio_general"] or 0) if totales else 0,
        "ultimas_actividades": [
            {
                "id": a["polar_id"],
                "fecha": a["fecha_inicio"],
                "tipo": a["tipo"],
                "distancia_km": a["distancia_km"],
                "duracion_minutos": int(a["duracion_segundos"] / 60),
                "duracion_texto": _formatear_duracion(a["duracion_segundos"]),
                "calorias": a["calorias"],
                "fc_promedio": a["fc_promedio"],
                "fc_maxima": a["fc_maxima"],
                "velocidad_media_kmh": a["velocidad_media_kmh"],
                "velocidad_maxima_kmh": a["velocidad_maxima_kmh"],
                "desnivel_positivo": a["desnivel_positivo"],
                "desnivel_negativo": a["desnivel_negativo"],
                "tiene_ruta": bool(a["tiene_ruta"]),
            }
            for a in ultimas
        ],
        "por_tipo": {
            t["tipo"]: {
                "count": t["count"],
                "km": round(t["km"], 2),
                "calorias": int(t["calorias"]),
                "duracion_minutos": int(t["duracion_segundos"] / 60),
            }
            for t in por_tipo
        },
    }


@ruta.get("/historial")
def historial_polar(limite: int = 30):
    """
    Lista las últimas N actividades deportivas, ordenadas por fecha descendente.
    """
    limite = min(limite, 200)

    total = bd.consultar_uno("SELECT COUNT(*) as total FROM actividades_polar")
    actividades = bd.consultar_todos(
        """
        SELECT polar_id, fecha_inicio, tipo, distancia_km,
               duracion_segundos, calorias, fc_promedio, fc_maxima,
               velocidad_media_kmh, velocidad_maxima_kmh,
               desnivel_positivo, desnivel_negativo, tiene_ruta
        FROM actividades_polar
        ORDER BY fecha_inicio DESC
        LIMIT ?
        """,
        (limite,),
    )

    return {
        "total": total["total"] if total else 0,
        "actividades": [
            {
                "id": a["polar_id"],
                "fecha": a["fecha_inicio"],
                "tipo": a["tipo"],
                "distancia_km": a["distancia_km"],
                "duracion_minutos": int(a["duracion_segundos"] / 60),
                "duracion_texto": _formatear_duracion(a["duracion_segundos"]),
                "calorias": a["calorias"],
                "fc_promedio": a["fc_promedio"],
                "fc_maxima": a["fc_maxima"],
                "velocidad_media_kmh": a["velocidad_media_kmh"],
                "velocidad_maxima_kmh": a["velocidad_maxima_kmh"],
                "desnivel_positivo": a["desnivel_positivo"],
                "desnivel_negativo": a["desnivel_negativo"],
                "tiene_ruta": bool(a["tiene_ruta"]),
            }
            for a in actividades
        ],
    }


@ruta.post("/sincronizar")
def sincronizar_manual():
    """
    Fuerza una sincronización inmediata con Polar Flow.
    Devuelve el número de actividades nuevas guardadas.
    """
    try:
        ejercicios = sincronizar_ejercicios()
        nuevos = _guardar_ejercicios(ejercicios)
        logger.info(f"Sincronización manual Polar: {nuevos} actividad(es) nueva(s)")
        return {
            "ok": True,
            "nuevas_actividades": nuevos,
            "proxima_programada": "en ~3 horas (automático)",
        }
    except Exception as e:
        logger.error(f"Error en sincronización manual Polar: {e}")
        raise HTTPException(500, "Error al sincronizar con Polar")


@ruta.get("/ejercicio/{polar_id}/ruta")
def cargar_ruta(polar_id: str):
    """
    Descarga el TCX de un ejercicio concreto y extrae velocidad máxima y desnivel.
    Solo se llama bajo demanda desde el frontend (botón por fila).
    Guarda los resultados en la BD para no volver a descargar.
    """
    ejercicio = bd.consultar_uno(
        "SELECT polar_id, tiene_ruta, velocidad_maxima_kmh, desnivel_positivo FROM actividades_polar WHERE polar_id = ?",
        (polar_id,),
    )
    if not ejercicio:
        raise HTTPException(404, f"Ejercicio no encontrado: {polar_id}")
    if not ejercicio["tiene_ruta"]:
        raise HTTPException(400, "Este ejercicio no tiene datos de ruta (sin GPS)")

    # Si ya están calculados, devolver directamente sin volver a descargar
    if ejercicio["desnivel_positivo"] is not None:
        return bd.consultar_uno(
            "SELECT velocidad_maxima_kmh, desnivel_positivo, desnivel_negativo FROM actividades_polar WHERE polar_id = ?",
            (polar_id,),
        )

    # Descargar TCX y calcular
    try:
        with httpx.Client(timeout=60) as cliente:
            datos_ruta = _obtener_datos_ruta(cliente, polar_id)
    except Exception as e:
        logger.error(f"Error descargando ruta de {polar_id}: {e}")
        raise HTTPException(500, "Error al descargar datos de ruta desde Polar")

    # Guardar en BD
    bd.ejecutar(
        """
        UPDATE actividades_polar
        SET velocidad_maxima_kmh = ?, desnivel_positivo = ?, desnivel_negativo = ?
        WHERE polar_id = ?
        """,
        (
            datos_ruta["velocidad_maxima_kmh"],
            datos_ruta["desnivel_positivo"],
            datos_ruta["desnivel_negativo"],
            polar_id,
        ),
    )
    logger.info(f"Ruta cargada para {polar_id}: {datos_ruta}")
    return datos_ruta


@ruta.put("/ejercicio/{polar_id}/ruta")
def guardar_ruta_manual(polar_id: str, datos: dict):
    """
    Guarda datos de ruta introducidos manualmente por el usuario.
    Acepta: velocidad_maxima_kmh, desnivel_positivo, desnivel_negativo.
    """
    ejercicio = bd.consultar_uno(
        "SELECT polar_id FROM actividades_polar WHERE polar_id = ?", (polar_id,)
    )
    if not ejercicio:
        raise HTTPException(404, f"Ejercicio no encontrado: {polar_id}")

    campos = {}
    if "velocidad_media_kmh"  in datos and datos["velocidad_media_kmh"]  is not None:
        campos["velocidad_media_kmh"]  = float(datos["velocidad_media_kmh"])
    if "velocidad_maxima_kmh" in datos and datos["velocidad_maxima_kmh"] is not None:
        campos["velocidad_maxima_kmh"] = float(datos["velocidad_maxima_kmh"])
    if "desnivel_positivo" in datos and datos["desnivel_positivo"] is not None:
        campos["desnivel_positivo"] = int(datos["desnivel_positivo"])
    if "desnivel_negativo" in datos and datos["desnivel_negativo"] is not None:
        campos["desnivel_negativo"] = int(datos["desnivel_negativo"])

    if not campos:
        raise HTTPException(400, "No se proporcionó ningún campo válido")

    sets = ", ".join(f"{k} = ?" for k in campos)
    bd.ejecutar(
        f"UPDATE actividades_polar SET {sets} WHERE polar_id = ?",
        (*campos.values(), polar_id),
    )
    logger.info(f"Ruta actualizada manualmente para {polar_id}: {campos}")
    return {"ok": True, "polar_id": polar_id, **campos}


def _guardar_ejercicios(ejercicios: list[dict]) -> int:
    """
    Inserta los ejercicios nuevos en la BD, ignorando duplicados (UNIQUE polar_id).
    Devuelve el número de filas insertadas.
    """
    nuevos = 0
    for ej in ejercicios:
        existente = bd.consultar_uno(
            "SELECT id FROM actividades_polar WHERE polar_id = ?",
            (ej["polar_id"],),
        )
        if existente:
            continue
        bd.ejecutar(
            """
            INSERT INTO actividades_polar
                (polar_id, fecha_inicio, fecha_subida, tipo, distancia_km,
                 duracion_segundos, calorias, fc_promedio, fc_maxima,
                 velocidad_media_kmh, tiene_ruta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ej["polar_id"],
                ej["fecha_inicio"],
                ej.get("fecha_subida"),
                ej["tipo"],
                ej.get("distancia_km"),
                ej["duracion_segundos"],
                ej.get("calorias"),
                ej.get("fc_promedio"),
                ej.get("fc_maxima"),
                ej.get("velocidad_media_kmh"),
                1 if ej.get("tiene_ruta") else 0,
            ),
        )
        nuevos += 1
    return nuevos
