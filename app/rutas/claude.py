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
    Recibe un evento de sesion de Claude Code y lo guarda en BD.
    Idempotente: si session_id existe, responde OK sin duplicar.
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
        logger.info(f"Sesion registrada: {evento.session_id} ({evento.proyecto})")
        return {
            "ok": True,
            "session_id": evento.session_id,
            "duplicada": False,
        }
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: tracking_claude.session_id" in str(e):
            logger.warning(f"Sesion duplicada (reintento): {evento.session_id}")
            return {
                "ok": True,
                "session_id": evento.session_id,
                "duplicada": True,
            }
        logger.error(f"Error BD en sesion {evento.session_id}: {e}")
        raise HTTPException(500, "Error al guardar la sesion")
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

    # Consultar agregaciones
    sql_agregacion = """
        SELECT
            COUNT(*) as total,
            COALESCE(SUM(input_tokens), 0) as input_total,
            COALESCE(SUM(output_tokens), 0) as output_total,
            COALESCE(SUM(cache_read_tokens), 0) as cache_read_total,
            COALESCE(SUM(cache_creation_tokens), 0) as cache_creation_total,
            COALESCE(SUM(coste_input_usd), 0.0) as coste_input,
            COALESCE(SUM(coste_output_usd), 0.0) as coste_output,
            COALESCE(SUM(coste_cache_usd), 0.0) as coste_cache,
            CASE WHEN COUNT(*) > 0 THEN
                ROUND(
                    (SUM(input_tokens) + SUM(output_tokens) +
                     SUM(cache_read_tokens) + SUM(cache_creation_tokens)) / COUNT(*), 0
                )
            ELSE 0 END as tokens_promedio
        FROM tracking_claude
        WHERE datetime(fecha_fin) BETWEEN ? AND ?
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
