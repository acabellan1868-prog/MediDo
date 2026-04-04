"""
MediDo — Rutas /api/claude.
Recoleccion y agregacion de datos de Claude Code desde Windows.
El hook de Claude Code (Fase 13a) envia eventos POST a /sesion.
"""

import sqlite3
import logging
from datetime import datetime, timedelta, date
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app import bd
from app.config import (
    CLAUDE_PRESUPUESTO_EUR,
    CLAUDE_DIA_RESETEO,
    CLAUDE_LIMITE_5H_TOKENS,
    CLAUDE_LIMITE_SEMANA_TOKENS,
)

logger = logging.getLogger("medido.claude")
ruta = APIRouter()


# ---- MODELOS PYDANTIC ----


class EventoClaudeCode(BaseModel):
    """Evento de uso de Claude Code (recibido del hook)."""

    session_id: str
    fecha_fin: str  # ISO 8601 con timezone
    directorio: Optional[str] = None
    proyecto: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    coste_input_usd: float
    coste_output_usd: float
    coste_cache_usd: float

    @field_validator("session_id")
    @classmethod
    def validar_session_id(cls, v: str) -> str:
        if not v or len(v) < 8:
            raise ValueError("session_id debe tener al menos 8 caracteres")
        if len(v) > 128:
            raise ValueError("session_id no puede exceder 128 caracteres")
        return v

    @field_validator("proyecto")
    @classmethod
    def validar_proyecto(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("proyecto no puede estar vacio")
        if len(v) > 256:
            raise ValueError("proyecto no puede exceder 256 caracteres")
        return v

    @field_validator("directorio")
    @classmethod
    def validar_directorio(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 512:
            raise ValueError("directorio no puede exceder 512 caracteres")
        return v

    @field_validator("fecha_fin")
    @classmethod
    def validar_fecha(cls, v: str) -> str:
        try:
            # Parsear ISO 8601 (SQLite soporta este formato)
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"fecha_fin debe ser ISO 8601, got {v}")
        return v

    @field_validator(
        "input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens",
        mode="before"
    )
    @classmethod
    def convertir_a_int(cls, v):
        if v is None:
            return 0
        return int(v) if v else 0

    @field_validator("coste_input_usd", "coste_output_usd", "coste_cache_usd", mode="before")
    @classmethod
    def convertir_a_float(cls, v):
        if v is None:
            return 0.0
        return float(v) if v else 0.0


# ---- ENDPOINTS ----


@ruta.post("/sesion")
def registrar_sesion(evento: EventoClaudeCode):
    """
    Recibe un evento de respuesta de Claude Code y lo guarda en BD.
    Cada respuesta de una sesión genera una fila independiente (sin UNIQUE en session_id).
    """
    sql = """
        INSERT INTO tracking_claude (
            session_id, fecha_fin, directorio, proyecto,
            input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
            coste_input_usd, coste_output_usd, coste_cache_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    parametros = (
        evento.session_id,
        evento.fecha_fin,
        evento.directorio,
        evento.proyecto,
        evento.input_tokens,
        evento.output_tokens,
        evento.cache_read_tokens,
        evento.cache_creation_tokens,
        evento.coste_input_usd,
        evento.coste_output_usd,
        evento.coste_cache_usd,
    )

    try:
        bd.ejecutar(sql, parametros)
        logger.info(f"Respuesta registrada: {evento.session_id} ({evento.proyecto})")
        return {"ok": True, "session_id": evento.session_id}
    except Exception as e:
        logger.error(f"Error inesperado en registrar_sesion: {e}")
        raise HTTPException(500, "Error interno del servidor")


@ruta.get("/resumen")
def resumen(
    periodo: Literal["dia", "semana", "mes"] = "mes",
    fecha_hasta: Optional[str] = None,
):
    """
    Devuelve resumen de uso de Claude Code en el periodo especificado.

    Query params:
    - periodo: 'dia' (24h), 'semana' (7 dias), 'mes' (defecto)
    - fecha_hasta: ISO 8601 (defecto: hoy)

    Responde con:
    - sesiones totales, tokens acumulados, coste total
    - promedio tokens por sesion
    - porcentaje del presupuesto (si CLAUDE_PRESUPUESTO_USD existe)
    - ultima sesion
    """

    # Parsear fecha_hasta
    if fecha_hasta:
        try:
            fecha_fin = datetime.fromisoformat(fecha_hasta.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, f"fecha_hasta invalida: {fecha_hasta}")
    else:
        fecha_fin = datetime.now()

    # Calcular rango de fechas segun el periodo
    if periodo == "dia":
        fecha_inicio = fecha_fin - timedelta(days=1)
        fecha_inicio = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        fecha_inicio = fecha_fin - timedelta(days=7)
        fecha_inicio = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "mes":
        # Logica de reseteo mensual
        if CLAUDE_DIA_RESETEO:
            hoy = fecha_fin.date()
            if hoy.day >= CLAUDE_DIA_RESETEO:
                # Estamos en el rango: desde CLAUDE_DIA_RESETEO de este mes
                mes_inicio = hoy.replace(day=CLAUDE_DIA_RESETEO)
            else:
                # Estamos antes del dia de reseteo: contar desde el mes anterior
                mes_anterior = hoy.replace(day=1) - timedelta(days=1)
                mes_inicio = mes_anterior.replace(day=CLAUDE_DIA_RESETEO)
            fecha_inicio = datetime.combine(mes_inicio, datetime.min.time())
        else:
            # Defecto: 1ro del mes
            mes_inicio = fecha_fin.date().replace(day=1)
            fecha_inicio = datetime.combine(mes_inicio, datetime.min.time())
    else:
        raise HTTPException(400, f"periodo invalido: {periodo}")

    # Asegurar que fecha_fin sea final del dia
    fecha_fin_str = (
        fecha_fin.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
    )
    fecha_inicio_str = (
        fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    )

    # Consultar agregaciones — agrupando por sesión para evitar sumar acumulados parciales
    sql_agregacion = """
        SELECT
            COUNT(*) as total,
            COALESCE(SUM(max_input), 0) as input_total,
            COALESCE(SUM(max_output), 0) as output_total,
            COALESCE(SUM(max_cache_read), 0) as cache_read_total,
            COALESCE(SUM(max_cache_creation), 0) as cache_creation_total,
            COALESCE(SUM(max_coste_input), 0.0) as coste_input,
            COALESCE(SUM(max_coste_output), 0.0) as coste_output,
            COALESCE(SUM(max_coste_cache), 0.0) as coste_cache,
            CASE WHEN COUNT(*) > 0 THEN
                ROUND(
                    (SUM(max_input) + SUM(max_output) +
                     SUM(max_cache_read) + SUM(max_cache_creation)) / COUNT(*), 0
                )
            ELSE 0 END as tokens_promedio
        FROM (
            SELECT
                session_id,
                MAX(input_tokens) as max_input,
                MAX(output_tokens) as max_output,
                MAX(cache_read_tokens) as max_cache_read,
                MAX(cache_creation_tokens) as max_cache_creation,
                MAX(coste_input_usd) as max_coste_input,
                MAX(coste_output_usd) as max_coste_output,
                MAX(coste_cache_usd) as max_coste_cache
            FROM tracking_claude
            WHERE datetime(fecha_fin) BETWEEN ? AND ?
            GROUP BY session_id
        )
    """

    resultado_agg = bd.consultar_uno(sql_agregacion, (fecha_inicio_str, fecha_fin_str))

    # Consultar ultima sesion
    sql_ultima = """
        SELECT session_id, proyecto, fecha_fin,
               coste_input_usd + coste_output_usd + coste_cache_usd as coste_total,
               input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens as tokens_total
        FROM tracking_claude
        WHERE datetime(fecha_fin) BETWEEN ? AND ?
        ORDER BY fecha_fin DESC
        LIMIT 1
    """
    ultima_sesion = bd.consultar_uno(sql_ultima, (fecha_inicio_str, fecha_fin_str))

    # Construir respuesta
    coste_total = (
        resultado_agg.get("coste_input", 0)
        + resultado_agg.get("coste_output", 0)
        + resultado_agg.get("coste_cache", 0)
    )

    respuesta = {
        "periodo": periodo,
        "fecha_desde": fecha_inicio.isoformat(),
        "fecha_hasta": fecha_fin.isoformat(),
        "sesiones_totales": resultado_agg["total"],
        "tokens": {
            "input_total": resultado_agg["input_total"],
            "output_total": resultado_agg["output_total"],
            "cache_read_total": resultado_agg["cache_read_total"],
            "cache_creation_total": resultado_agg["cache_creation_total"],
            "promedio_por_sesion": (
                resultado_agg["tokens_promedio"] if resultado_agg["total"] > 0 else 0
            ),
        },
        "coste": {
            "input_usd": round(resultado_agg["coste_input"], 5),
            "output_usd": round(resultado_agg["coste_output"], 5),
            "cache_usd": round(resultado_agg["coste_cache"], 5),
            "total_usd": round(coste_total, 5),
        },
    }

    # Agregar limites de tokens (últimas 5h y semana)
    hace_5h = fecha_fin - timedelta(hours=5)
    hace_7d = fecha_fin - timedelta(days=7)

    sql_5h = """
        SELECT COALESCE(SUM(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens), 0) as tokens_total
        FROM tracking_claude
        WHERE datetime(fecha_fin) > ?
    """
    resultado_5h = bd.consultar_uno(sql_5h, (hace_5h.isoformat(),))
    tokens_5h = resultado_5h.get("tokens_total", 0) if resultado_5h else 0

    sql_7d = """
        SELECT COALESCE(SUM(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens), 0) as tokens_total
        FROM tracking_claude
        WHERE datetime(fecha_fin) > ?
    """
    resultado_7d = bd.consultar_uno(sql_7d, (hace_7d.isoformat(),))
    tokens_7d = resultado_7d.get("tokens_total", 0) if resultado_7d else 0

    pct_5h = (tokens_5h / CLAUDE_LIMITE_5H_TOKENS * 100) if CLAUDE_LIMITE_5H_TOKENS > 0 else 0
    pct_7d = (tokens_7d / CLAUDE_LIMITE_SEMANA_TOKENS * 100) if CLAUDE_LIMITE_SEMANA_TOKENS > 0 else 0

    respuesta["limites_tokens"] = {
        "ultimas_5h": {
            "tokens_usados": tokens_5h,
            "limite": CLAUDE_LIMITE_5H_TOKENS,
            "porcentaje_usado": round(pct_5h, 1),
        },
        "ultima_semana": {
            "tokens_usados": tokens_7d,
            "limite": CLAUDE_LIMITE_SEMANA_TOKENS,
            "porcentaje_usado": round(pct_7d, 1),
        },
    }

    # Agregar presupuesto si esta configurado
    if CLAUDE_PRESUPUESTO_EUR:
        porcentaje = (
            (coste_total / CLAUDE_PRESUPUESTO_EUR * 100)
            if CLAUDE_PRESUPUESTO_EUR > 0
            else 0
        )
        saldo = CLAUDE_PRESUPUESTO_EUR - coste_total

        # Calcular dias restantes hasta proximo reseteo
        if periodo == "mes" and CLAUDE_DIA_RESETEO:
            hoy = fecha_fin.date()
            proximo_reseteo = hoy.replace(day=CLAUDE_DIA_RESETEO)
            if hoy >= proximo_reseteo:
                # Agregar un mes
                if proximo_reseteo.month == 12:
                    proximo_reseteo = proximo_reseteo.replace(
                        year=proximo_reseteo.year + 1, month=1
                    )
                else:
                    proximo_reseteo = proximo_reseteo.replace(
                        month=proximo_reseteo.month + 1
                    )
            dias_restantes = (proximo_reseteo - hoy).days
        else:
            dias_restantes = None

        respuesta["presupuesto"] = {
            "presupuesto_eur": CLAUDE_PRESUPUESTO_EUR,
            "porcentaje_usado": round(porcentaje, 1),
            "saldo_eur": round(saldo, 5),
        }
        if dias_restantes is not None:
            respuesta["presupuesto"]["dias_restantes"] = dias_restantes

    # Agregar ultima sesion si existe
    if ultima_sesion:
        respuesta["ultima_sesion"] = {
            "session_id": ultima_sesion["session_id"],
            "proyecto": ultima_sesion["proyecto"],
            "fecha_fin": ultima_sesion["fecha_fin"],
            "coste_usd": round(ultima_sesion["coste_total"], 5),
            "tokens_total": ultima_sesion["tokens_total"],
        }

    return respuesta


@ruta.delete("/sesiones/{session_id}")
def eliminar_sesion(session_id: str):
    """Elimina todas las respuestas de una sesión de la BD por su session_id."""
    resultado = bd.consultar_uno(
        "SELECT session_id FROM tracking_claude WHERE session_id = ?", (session_id,)
    )
    if not resultado:
        raise HTTPException(404, f"Sesión no encontrada: {session_id}")
    bd.ejecutar("DELETE FROM tracking_claude WHERE session_id = ?", (session_id,))
    logger.info(f"Sesión eliminada: {session_id}")
    return {"ok": True, "session_id": session_id}


@ruta.get("/sesiones")
def listar_sesiones(
    periodo: Literal["dia", "semana", "mes"] = "mes",
    proyecto: Optional[str] = None,
    limite: int = 1000,
):
    """
    Lista sesiones de Claude Code agrupadas por session_id, con filtros opcionales.
    Cada sesión muestra los tokens/coste del acumulado máximo (última respuesta)
    y el número de respuestas registradas.

    Query params:
    - periodo: 'dia' (24h), 'semana' (7 dias), 'mes' (defecto)
    - proyecto: nombre de proyecto para filtrar (opcional)
    - limite: máximo de sesiones a devolver (defecto: 1000, máximo: 10000)

    Responde con:
    - sesiones: una fila por session_id con totales y num_respuestas
    - totales: sesiones únicas, tokens totales y coste total del período
    - rango: fechas desde/hasta del período seleccionado
    - proyectos_unicos: lista de proyectos para el dropdown
    """

    limite = min(limite, 10000)
    fecha_fin = datetime.now()

    if periodo == "dia":
        fecha_inicio = fecha_fin - timedelta(days=1)
        fecha_inicio = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        fecha_inicio = fecha_fin - timedelta(days=7)
        fecha_inicio = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "mes":
        if CLAUDE_DIA_RESETEO:
            hoy = fecha_fin.date()
            if hoy.day >= CLAUDE_DIA_RESETEO:
                mes_inicio = hoy.replace(day=CLAUDE_DIA_RESETEO)
            else:
                mes_anterior = hoy.replace(day=1) - timedelta(days=1)
                mes_inicio = mes_anterior.replace(day=CLAUDE_DIA_RESETEO)
            fecha_inicio = datetime.combine(mes_inicio, datetime.min.time())
        else:
            mes_inicio = fecha_fin.date().replace(day=1)
            fecha_inicio = datetime.combine(mes_inicio, datetime.min.time())
    else:
        raise HTTPException(400, f"periodo invalido: {periodo}")

    fecha_fin_str = fecha_fin.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
    fecha_inicio_str = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    where = ["datetime(fecha_fin) BETWEEN ? AND ?"]
    parametros = [fecha_inicio_str, fecha_fin_str]
    if proyecto:
        where.append("proyecto = ?")
        parametros.append(proyecto)
    where_clause = " WHERE " + " AND ".join(where)

    # Una fila por sesión: máximos acumulados + conteo de respuestas
    sql_sesiones = f"""
        SELECT
            session_id,
            MAX(fecha_fin) as fecha_fin,
            proyecto,
            MAX(input_tokens) as input_tokens,
            MAX(output_tokens) as output_tokens,
            MAX(cache_read_tokens) as cache_read_tokens,
            MAX(cache_creation_tokens) as cache_creation_tokens,
            MAX(coste_input_usd + coste_output_usd + coste_cache_usd) as coste_total,
            COUNT(*) as num_respuestas
        FROM tracking_claude
        {where_clause}
        GROUP BY session_id
        ORDER BY MAX(fecha_fin) DESC
        LIMIT ?
    """
    sesiones_raw = bd.consultar_todos(sql_sesiones, tuple(parametros + [limite]))

    # Totales calculados sobre los máximos por sesión (evita sumar acumulados parciales)
    sql_agg = f"""
        SELECT
            COUNT(DISTINCT session_id) as sesiones_count,
            COALESCE(SUM(max_tokens), 0) as tokens_total,
            COALESCE(SUM(max_coste), 0) as coste_total
        FROM (
            SELECT
                session_id,
                MAX(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens) as max_tokens,
                MAX(coste_input_usd + coste_output_usd + coste_cache_usd) as max_coste
            FROM tracking_claude
            {where_clause}
            GROUP BY session_id
        )
    """
    agg = bd.consultar_uno(sql_agg, tuple(parametros))

    sql_proyectos = """
        SELECT DISTINCT proyecto
        FROM tracking_claude
        WHERE datetime(fecha_fin) BETWEEN ? AND ?
        ORDER BY proyecto
    """
    proyectos_raw = bd.consultar_todos(sql_proyectos, (fecha_inicio_str, fecha_fin_str))
    proyectos_unicos = [p["proyecto"] for p in proyectos_raw]

    sesiones = []
    for s in sesiones_raw:
        sesiones.append({
            "session_id": s["session_id"],
            "fecha_fin": s["fecha_fin"],
            "proyecto": s["proyecto"],
            "input_tokens": s["input_tokens"],
            "output_tokens": s["output_tokens"],
            "cache_read_tokens": s["cache_read_tokens"],
            "cache_creation_tokens": s["cache_creation_tokens"],
            "coste_total_usd": round(s["coste_total"], 5),
            "num_respuestas": s["num_respuestas"],
        })

    return {
        "sesiones": sesiones,
        "totales": {
            "sesiones_count": agg.get("sesiones_count", 0) if agg else 0,
            "tokens_total": agg.get("tokens_total", 0) if agg else 0,
            "coste_total_usd": round(agg.get("coste_total", 0), 5) if agg else 0.0,
        },
        "rango": {
            "fecha_desde": fecha_inicio_str,
            "fecha_hasta": fecha_fin_str,
        },
        "proyectos_unicos": proyectos_unicos,
    }


@ruta.get("/sesiones/{session_id}")
def detalle_sesion(session_id: str):
    """
    Devuelve todas las respuestas individuales de una sesión, ordenadas cronológicamente.
    Usado para el desglose expandible en la tabla de sesiones.
    """
    respuestas_raw = bd.consultar_todos(
        """
        SELECT fecha_fin, input_tokens, output_tokens,
               cache_read_tokens, cache_creation_tokens,
               coste_input_usd + coste_output_usd + coste_cache_usd as coste_total
        FROM tracking_claude
        WHERE session_id = ?
        ORDER BY fecha_fin ASC
        """,
        (session_id,),
    )
    if not respuestas_raw:
        raise HTTPException(404, f"Sesión no encontrada: {session_id}")

    return {
        "session_id": session_id,
        "respuestas": [
            {
                "fecha_fin": r["fecha_fin"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "cache_read_tokens": r["cache_read_tokens"],
                "cache_creation_tokens": r["cache_creation_tokens"],
                "coste_total_usd": round(r["coste_total"], 5),
            }
            for r in respuestas_raw
        ],
    }
